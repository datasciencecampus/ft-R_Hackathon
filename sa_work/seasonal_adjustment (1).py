
"""
seasonal_adjustment.py — Seasonal adjustment utilities aiming to be a practical
replacement for common JDemetra+ workflows for monthly data (with UK-specific
working-day calendar, trading-day & Easter effects) and an optional X-13 path
for closer matching results.

Key features
------------
- Monthly focus (also supports quarterly) with UK working-day calendar.
- Deterministic regressors: trading-day (6-variable), length-of-month, Easter.
- Optional UK bank-holiday adjustment in trading-day counts.
- Outlier mitigation via Hampel filter.
- Seasonal adjustment via robust STL (fallback) or X-13ARIMA-SEATS if available.
- Optional automatic ARIMA identification using pmdarima (if installed) for
  diagnostics and as a guide when X-13 is unavailable.

Notes on matching JDemetra+
---------------------------
- For the closest match, prefer the X-13 path (requires the X-13 binary that
  statsmodels can locate). This module pre-adjusts calendar effects by OLS, then
  delegates seasonal extraction to X-13 when available.
- Exact parity with TRAMO/SEATS model selection is not guaranteed here. If you
  must match exactly, ensure X-13 is available and use method="x13".

"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple, List

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.seasonal import STL

# Optional: X-13ARIMA-SEATS via statsmodels; requires local X-13 binary
try:
    from statsmodels.tsa.x13 import x13_arima_analysis  # type: ignore
    _HAS_X13 = True
except Exception:
    _HAS_X13 = False

# Optional: pmdarima for automatic ARIMA identification (if installed)
try:
    import pmdarima as pm  # type: ignore
    _HAS_PM = True
except Exception:
    _HAS_PM = False

# Easter from pandas for Easter regressor
try:
    from pandas.tseries.holiday import Easter  # type: ignore
    _HAS_EASTER = True
except Exception:
    _HAS_EASTER = False

# ---------------------- Dataclass for results ----------------------
@dataclass
class SAResult:
    sa: pd.Series                     # Seasonally adjusted series
    seasonal: pd.Series               # Seasonal component (mult or add depending on transform)
    trend: pd.Series                  # Trend from STL (NaN in X-13 path)
    irregular: pd.Series              # Remainder from STL (NaN in X-13 path)
    model: str                        # 'stl' or 'x13'
    used_exog: Optional[pd.DataFrame] # Calendar regressors actually used
    coef: Optional[pd.Series]         # OLS coefficients for exog (if used)
    diagnostics: Dict[str, Any]       # Misc diagnostics

# ---------------------- UK Bank Holidays (England & Wales) ----------------------
# This covers standard recurring rules. Exceptional one-off holidays (e.g., jubilees) are not included
# by default. You can pass extra dates via `extra_uk_holidays` in the API if needed.

def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> pd.Timestamp:
    """Return the date of the n-th weekday (0=Mon..6=Sun) of a specific month."""
    d = pd.Timestamp(year=year, month=month, day=1)
    # Advance to first "weekday"
    days_ahead = (weekday - d.weekday()) % 7
    first = d + pd.Timedelta(days=days_ahead)
    return first + pd.Timedelta(days=7*(n-1))

def _last_weekday_of_month(year: int, month: int, weekday: int) -> pd.Timestamp:
    d = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
    days_back = (d.weekday() - weekday) % 7
    return d - pd.Timedelta(days=days_back)

def _observed(date: pd.Timestamp) -> pd.Timestamp:
    """Apply UK bank holiday substitution if holiday falls on weekend.
    - If Saturday -> observed Monday (two days later)
    - If Sunday -> observed Monday (one day later)
    - If Monday-Friday -> same day
    """
    if date.weekday() == 5:  # Saturday
        return date + pd.Timedelta(days=2)
    if date.weekday() == 6:  # Sunday
        return date + pd.Timedelta(days=1)
    return date

def uk_bank_holidays_engwales(start: pd.Timestamp, end: pd.Timestamp, extra: Optional[List[pd.Timestamp]] = None) -> pd.DatetimeIndex:
    """Generate standard UK (England & Wales) bank holidays between start and end (inclusive).

    Includes:
    - New Year's Day (observed)
    - Good Friday
    - Easter Monday
    - Early May bank holiday (first Monday in May)
    - Spring bank holiday (last Monday in May)
    - Summer bank holiday (last Monday in August)
    - Christmas Day (observed)
    - Boxing Day (observed)

    Notes: Special one-off holidays (e.g., jubilees, funerals, coronations) are not included.
    Add them via `extra` if needed.
    """
    years = range(start.year, end.year + 1)
    hols = []
    for y in years:
        # New Year's Day (observed)
        nyd = _observed(pd.Timestamp(year=y, month=1, day=1))
        # Easter related
        if _HAS_EASTER:
            easter = pd.Timestamp(Easter()(y))
        else:
            # Simple algorithmic fallback for Easter Sunday (Meeus/Jones/Butcher not implemented here)
            # Use pandas if available; if not, skip Good Friday/Easter Monday.
            easter = None
        if easter is not None:
            good_friday = easter - pd.Timedelta(days=2)
            easter_monday = easter + pd.Timedelta(days=1)
        else:
            good_friday = None
            easter_monday = None
        # Early May bank holiday: first Monday in May
        early_may = _nth_weekday_of_month(y, 5, weekday=0, n=1)
        # Spring bank: last Monday in May
        spring_bank = _last_weekday_of_month(y, 5, weekday=0)
        # Summer bank: last Monday in August
        summer_bank = _last_weekday_of_month(y, 8, weekday=0)
        # Christmas (observed)
        christmas = _observed(pd.Timestamp(year=y, month=12, day=25))
        # Boxing Day (observed): if Christmas observed on Monday (26th actual), Boxing moves to Tuesday
        boxing_raw = pd.Timestamp(year=y, month=12, day=26)
        boxing = _observed(boxing_raw)
        # If Christmas observed shifted Boxing further? UK rules cause occasional overlaps; adjust:
        if boxing == christmas:
            boxing = boxing + pd.Timedelta(days=1)

        for d in [nyd, good_friday, easter_monday, early_may, spring_bank, summer_bank, christmas, boxing]:
            if d is not None:
                hols.append(d)

    hols = pd.DatetimeIndex(sorted(set([d for d in hols if start <= d <= end])))
    if extra:
        extra_idx = pd.DatetimeIndex([pd.Timestamp(x) for x in extra])
        hols = hols.union(extra_idx[(extra_idx >= start) & (extra_idx <= end)])
    return hols

# ---------------------- Calendar Regressors ----------------------

def _infer_periods(y: pd.Series, seasonal_periods: Optional[int]) -> int:
    if seasonal_periods is not None:
        return seasonal_periods
    freq = getattr(y.index, "freqstr", None) or pd.infer_freq(y.index)
    if freq is None:
        raise ValueError("Cannot infer frequency. Please set `seasonal_periods`." )
    f = freq.upper()
    if f.startswith("M"):
        return 12
    if f.startswith("Q"):
        return 4
    raise ValueError(f"Unsupported frequency '{freq}'. Use monthly or quarterly.")


def _days_in_month(ts: pd.Timestamp) -> int:
    return (ts + pd.offsets.MonthEnd(0)).day


def _count_weekdays_uk(index: pd.DatetimeIndex, use_uk_holidays: bool = True,
                       extra_uk_holidays: Optional[List[pd.Timestamp]] = None) -> pd.DataFrame:
    """Count weekdays Mon..Sat relative to Sunday per period, optionally subtracting UK bank holidays.
    Returns DataFrame with columns Mon..Sat (each centered), and len (days-in-month centered).
    This supports monthly and quarterly indices.
    """
    if index.freq is None:
        inferred = pd.infer_freq(index)
        if inferred is None:
            raise ValueError("Index frequency is missing. Please set a fixed frequency.")
        index = index.asfreq(inferred)

    if index.freqstr.upper().startswith("M"):
        periods = index.to_period("M")
        freq = 'M'
    elif index.freqstr.upper().startswith("Q"):
        periods = index.to_period("Q")
        freq = 'Q'
    else:
        raise ValueError("Trading-day regressors only implemented for monthly/quarterly.")

    rows = []
    for p in periods.unique():
        if freq == 'M':
            start = p.to_timestamp(how='start')
            end = p.to_timestamp(how='end')
        else:
            start = p.start_time
            end = p.end_time
        dr = pd.date_range(start, end, freq='D')
        # Subtract UK bank holidays that fall Mon-Fri
        if use_uk_holidays:
            hols = uk_bank_holidays_engwales(start, end, extra=extra_uk_holidays)
            dr_work = dr.difference(hols)
        else:
            dr_work = dr
        counts = dr_work.weekday.value_counts().reindex(range(7), fill_value=0)
        td = counts.loc[0:5].values - counts.loc[6]  # Mon..Sat minus Sun
        rows.append((p.to_timestamp(how='end'), *td, len(dr)))

    df = pd.DataFrame(rows, columns=["period_end", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "days"])
    df.set_index("period_end", inplace=True)

    td_cols = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    df[td_cols] = df[td_cols] - df[td_cols].mean(axis=0)
    df["len"] = df["days"] - df["days"].mean()
    df.drop(columns=["days"], inplace=True)
    return df.reindex(index)


def _easter_regressor(index: pd.DatetimeIndex, k: int = 8) -> pd.Series:
    if not _HAS_EASTER:
        raise ImportError("pandas.tseries.holiday.Easter not available.")
    if index.freqstr is None:
        inferred = pd.infer_freq(index)
        if inferred is None:
            raise ValueError("Index frequency is missing. Please set a fixed frequency.")
        index = index.asfreq(inferred)
    if index.freqstr.upper().startswith("M"):
        to_period = "M"
    elif index.freqstr.upper().startswith("Q"):
        to_period = "Q"
    else:
        raise ValueError("Easter regressor is implemented for monthly/quarterly data.")
    periods = index.to_period(to_period)
    out = pd.Series(0.0, index=index)
    for p in periods.unique():
        if to_period == "M":
            start = p.to_timestamp(how="start"); end = p.to_timestamp(how="end")
        else:
            start = p.start_time; end = p.end_time
        easter_date = pd.Timestamp(Easter()(p.year))
        window_start = easter_date - pd.Timedelta(days=k)
        window_end = easter_date
        overlap_start = max(start, window_start)
        overlap_end = min(end, window_end)
        if overlap_start <= overlap_end:
            days_in_window = (window_end - window_start).days + 1
            days_in_period = (overlap_end - overlap_start).days + 1
            frac = days_in_period / max(days_in_window, 1)
        else:
            frac = 0.0
        out.loc[index[(index >= start) & (index <= end)]] = frac
    return (out - out.mean()).rename("Easter")

# ---------------------- Outlier mitigation ----------------------

def _hampel_filter(x: pd.Series, window: int = 7, n_sigmas: float = 3.0) -> Tuple[pd.Series, pd.Series]:
    x = x.astype('float64')
    med = x.rolling(window, center=True, min_periods=1).median()
    mad = (np.abs(x - med)).rolling(window, center=True, min_periods=1).median()
    threshold = n_sigmas * 1.4826 * mad.replace(0, np.nan)
    outliers = (np.abs(x - med) > threshold).fillna(False)
    cleaned = x.copy()
    cleaned[outliers] = med[outliers]
    return cleaned, outliers

# ---------------------- Main API ----------------------

def seasonal_adjust(
    y: pd.Series,
    *,
    method: str = "auto",           # 'auto' | 'stl' | 'x13'
    multiplicative: bool = True,
    use_log: Optional[bool] = None,  # If None: auto (True if y>0 and multiplicative)
    robust_stl: bool = True,
    outlier_method: str = "hampel",  # 'none' | 'hampel'
    outlier_window: int = 7,
    outlier_sigmas: float = 3.0,
    use_trading_day: bool = True,
    use_length_effect: bool = True,
    use_easter: bool = True,
    easter_k: int = 8,
    use_uk_working_days: bool = True,
    extra_uk_holidays: Optional[List[pd.Timestamp]] = None,
    extra_exog: Optional[pd.DataFrame] = None,
    seasonal_periods: Optional[int] = None,
) -> SAResult:
    """
    Seasonally adjust a monthly (or quarterly) time series with UK calendar effects.

    Parameters
    ----------
    y : pd.Series
        Monthly (preferred) or quarterly series with a fixed DatetimeIndex.
    method : {'auto','stl','x13'}
        'auto' uses X-13 if available; else STL.
    multiplicative : bool
        Interpret seasonality multiplicatively (log transform when possible).
    use_log : bool or None
        If None, enable log when y>0 and multiplicative=True.
    robust_stl : bool
        Use robust STL.
    outlier_method : {'none','hampel'}
        Hampel filter on working residuals.
    use_trading_day, use_length_effect, use_easter : bool
        Deterministic calendar regressors.
    easter_k : int
        Pre-Easter window length in days for Easter regressor.
    use_uk_working_days : bool
        If True, UK bank holidays are removed from weekday counts.
    extra_uk_holidays : list of timestamps
        Additional one-off holidays to remove from counts.
    extra_exog : pd.DataFrame
        Extra regressors aligned to y.index.
    seasonal_periods : int or None
        12 for monthly, 4 for quarterly; inferred if None.

    Returns
    -------
    SAResult
    """
    if not isinstance(y.index, pd.DatetimeIndex):
        raise TypeError("`y` must have a pandas DatetimeIndex.")
    y = y.sort_index()
    if y.index.freq is None:
        inferred = pd.infer_freq(y.index)
        if inferred is None:
            raise ValueError("Cannot infer index frequency. Please set y.index.freq.")
        y = y.asfreq(inferred)

    s = _infer_periods(y, seasonal_periods)

    # Decide log-transform
    if use_log is None:
        use_log = multiplicative and (y.min() > 0)
    wy = np.log(y) if use_log else y.astype('float64')

    # Build calendar regressors (monthly/quarterly only)
    exog_parts = []
    exog_notes = []
    if y.index.freqstr.upper().startswith(("M", "Q")):
        if use_trading_day or use_length_effect:
            td_len = _count_weekdays_uk(y.index, use_uk_holidays=use_uk_working_days,
                                        extra_uk_holidays=extra_uk_holidays)
            cols = []
            if use_trading_day:
                cols += ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
                exog_notes.append("trading_day_uk")
            if use_length_effect:
                cols += ["len"]
                exog_notes.append("length")
            exog_parts.append(td_len[cols])
        if use_easter:
            exog_parts.append(_easter_regressor(y.index, k=easter_k).to_frame("Easter"))
            exog_notes.append("easter")
    if extra_exog is not None:
        exog_parts.append(extra_exog.reindex(y.index))
        exog_notes.append("extra_exog")

    X = None
    if exog_parts:
        X = pd.concat(exog_parts, axis=1).fillna(0.0)
        X = X - X.mean()  # center

    # OLS to remove deterministic effects
    coef = None
    if X is not None and X.shape[1] > 0:
        X_ols = sm.add_constant(X)
        ols = sm.OLS(wy.values, X_ols.values, missing='drop').fit()
        coef = pd.Series(ols.params, index=X_ols.columns, name='coef')
        fitted_det = pd.Series(ols.fittedvalues, index=wy.index, name='deterministic_fit')
        resid = wy - fitted_det
    else:
        fitted_det = pd.Series(0.0, index=wy.index, name='deterministic_fit')
        resid = wy.copy()

    # Outlier mitigation
    outlier_mask = pd.Series(False, index=y.index)
    if outlier_method == 'hampel':
        resid, outlier_mask = _hampel_filter(resid, window=outlier_window, n_sigmas=outlier_sigmas)

    chosen_method = None
    trend = pd.Series(np.nan, index=wy.index, name='trend')
    irregular = pd.Series(np.nan, index=wy.index, name='irregular')

    # Optional: automatic ARIMA identification for diagnostics (not directly used by X-13)
    arima_summary = None
    if _HAS_PM:
        try:
            m = s
            auto = pm.auto_arima(resid.dropna(), seasonal=True, m=m, information_criterion='aicc',
                                 stepwise=True, suppress_warnings=True, error_action='ignore',
                                 with_intercept=True)
            arima_summary = str(auto.summary())
        except Exception:
            arima_summary = None

    # X-13 path: apply seasonal extraction on pre-adjusted series
    sa_w = None
    seasonal_comp = None
    if (method in ("auto", "x13")) and _HAS_X13:
        try:
            x13_res = x13_arima_analysis(resid.dropna())
            # seasadj (on working series) = resid - seasonal
            sa_w = x13_res.seasadj.reindex(resid.index)
            # Reconstruct seasonal (working series seasonal)
            seasonal_comp = (resid - sa_w).rename('seasonal')
            chosen_method = 'x13'
        except Exception:
            chosen_method = None

    # STL fallback
    if chosen_method is None:
        stl = STL(resid, period=s, robust=robust_stl, seasonal=13, trend=max(7, s+1)).fit()
        seasonal_comp = stl.seasonal.rename('seasonal')
        trend = stl.trend.rename('trend')
        irregular = stl.resid.rename('irregular')
        sa_w = (resid - seasonal_comp).rename('sa_w')
        chosen_method = 'stl'

    # Recombine deterministic part and undo transform
    sa = sa_w + fitted_det
    if use_log:
        sa = np.exp(sa)
        # For multiplicative interpretation, seasonal factor on original scale
        seasonal_out = np.exp(seasonal_comp)
    else:
        seasonal_out = seasonal_comp

    diagnostics = {
        'method': chosen_method,
        'seasonal_periods': s,
        'used_log': bool(use_log),
        'multiplicative': bool(multiplicative),
        'outliers_flagged': int(outlier_mask.sum()) if outlier_method == 'hampel' else 0,
        'exog_included': exog_notes,
        'index_freq': y.index.freqstr,
        'auto_arima_summary': arima_summary,
    }

    return SAResult(
        sa=sa.rename('sa'),
        seasonal=seasonal_out.rename('seasonal'),
        trend=trend,
        irregular=irregular,
        model=chosen_method,
        used_exog=(X if X is not None and X.shape[1] > 0 else None),
        coef=coef,
        diagnostics=diagnostics,
    )

# ---------------------- Convenience plotting (optional) ----------------------

def plot_sa(y: pd.Series, res: SAResult, title: str = "Seasonal Adjustment"):
    """Quick plot comparing original and seasonally adjusted series."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 5))
    y.plot(ax=ax, alpha=0.5, label='Original')
    res.sa.plot(ax=ax, label='Seasonally adjusted')
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    return fig, ax

