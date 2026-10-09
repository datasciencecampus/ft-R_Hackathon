import argparse
from .pipeline import run_pipeline
def main():
 p=argparse.ArgumentParser()
 for n in ["nspl","addressbase","visa","config","output"]: p.add_argument(f"--{n}",required=True)
 a=p.parse_args(); run_pipeline(nspl_path=a.nspl,addressbase_path=a.addressbase,visa_path=a.visa,config_path=a.config,output_dir=a.output)
if __name__=="__main__": main()
