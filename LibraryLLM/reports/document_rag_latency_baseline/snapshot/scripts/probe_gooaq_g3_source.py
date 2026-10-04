"""Inspect live GooAQ card/schema before bounded streaming download."""
import os
import traceback
from gooaq_g3_controls import CACHE, TRAIN, verify, write
os.environ['HF_HOME']=str(CACHE)
os.environ['HF_DATASETS_CACHE']=str(CACHE/'datasets')
from huggingface_hub import HfApi,hf_hub_download
from datasets import get_dataset_config_names,load_dataset_builder
def main():
    verify()
    result={'dataset_id':'sentence-transformers/gooaq','url':'https://huggingface.co/datasets/sentence-transformers/gooaq','cache':str(CACHE)}
    try:
        info=HfApi().dataset_info(result['dataset_id'],timeout=30)
        result.update(revision=info.sha,gated=info.gated,private=info.private)
        result['card_path']=hf_hub_download(result['dataset_id'],'README.md',repo_type='dataset',revision=info.sha,cache_dir=str(CACHE/'hub'))
        configs=get_dataset_config_names(result['dataset_id'],revision=info.sha)
        result['configs']=configs
        result['schemas']={}
        for config in configs:
            b=load_dataset_builder(result['dataset_id'],name=config,revision=info.sha,cache_dir=str(CACHE/'datasets'))
            result['schemas'][config]={'features':{c:b.info.features[c].dtype for c in b.info.features},'splits':{s:{'rows':v.num_examples,'bytes':v.num_bytes} for s,v in b.info.splits.items()}}
        result['status']='accessible'
    except Exception as e:result.update(status='FAILED_STOP',error_type=type(e).__name__,error=str(e),traceback=traceback.format_exc())
    write(TRAIN/'reports/rag_g3_gooaq_source_probe.json',result)
    print(__import__('json').dumps(result,indent=2),flush=True)
    if result['status']!='accessible':raise RuntimeError('GooAQ source access failed; STOP')
if __name__=='__main__':main()
