"""Reproduce the curated DuReader-robust subset from its official archive.
Download happens only when explicitly running this script. No model/product calls.
"""
import argparse,hashlib,json,tarfile,urllib.request,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCENARIOS=['文件格式释义','专业软件术语','历史事实查询','作品信息查询','基础概念查询']
def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def prepare(output=None, archive=None):
    output=Path(output) if output else ROOT/'evaluator/dataset'
    manifest=json.loads((ROOT/'evaluator/dataset/download_manifest.json').read_text(encoding='utf-8'))
    if (output/'tasks.json').exists():raise FileExistsError('目录已有任务集，请保留已有材料；需要重建时使用新的--output目录')
    output.mkdir(parents=True,exist_ok=True);raw=output/'raw';raw.mkdir(exist_ok=True)
    target=raw/'dureader_robust-data.tar.gz'
    if archive:
        if Path(archive).resolve()!=target.resolve():shutil.copy2(archive,target)
    elif not target.exists():
        part=target.with_suffix('.part')
        with urllib.request.urlopen(manifest['download_url'],timeout=45) as response,part.open('wb') as handle:
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                handle.write(chunk)
        part.rename(target)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    if digest!=manifest['archive_sha256']:raise ValueError('官方包内容与已记录SHA256不同；请保留原版本并调查，不自动接受新内容')
    with tarfile.open(target) as tf:
        for name in ['dev.json','README.md','License.docx']:
            (raw/name).write_bytes(tf.extractfile('dureader_robust-data/'+name).read())
    if hashlib.sha256((raw/'dev.json').read_bytes()).hexdigest()!=manifest['dev_sha256']:raise ValueError('开发集哈希不同')
    source=json.loads((raw/'dev.json').read_text(encoding='utf-8'))
    indexed={q['id']:(i,j,q,p['context']) for i,d in enumerate(source['data']) for j,p in enumerate(d['paragraphs']) for q in p['qas']}
    materials=output/'materials';materials.mkdir(exist_ok=True);tasks=[];documents=[];reviews=[];selected=[]
    for n,qid in enumerate(manifest['selected_question_ids'],1):
        i,j,q,context=indexed[qid];tid=f'DU{n:03d}';filename=tid+'_context.txt'
        answers=list(dict.fromkeys(a['text'] for a in q['answers']))
        if not all(a in context for a in answers):raise ValueError('参考答案没有原文支持：'+qid)
        body=f'文档名称：{filename}\n资料来源：DuReader-robust dev；样本ID：{qid}\n'+context+'\n'
        (materials/filename).write_text(body,encoding='utf-8')
        spans=[dict(text=a,computed_context_start=context.index(a),computed_context_end=context.index(a)+len(a),original_answer_start=next(z['answer_start'] for z in q['answers'] if z['text']==a),support_excerpt=context[max(0,context.index(a)-45):min(len(context),context.index(a)+len(a)+65)]) for a in answers]
        documents.append(dict(id=filename,path='materials/'+filename,remote_names=[filename]))
        tasks.append(dict(id=tid,scenario=SCENARIOS[n-1],question='请根据本次上传的公开语料回答：'+q['question'],personas=['quick_lookup','source_checker'],kind='dataset_qa',requires_human_review=True,oracle=dict(required_groups=[],forbidden_phrases=[],expect_uncertainty=False),reference_answers=answers,reference_document_ids=[filename],provenance=dict(source_dataset='DuReader-robust',split='dev',original_question_id=qid,original_question=q['question'],source_data_index=i,source_paragraph_index=j,reference_exactly_in_documents=True,answer_spans=spans)))
        reviews.append(dict(task_id=tid,original_question=q['question'],reference_answers=answers,document_name=filename,context_length=len(context),material_sha256=hashlib.sha256((materials/filename).read_bytes()).hexdigest(),reference_span_check='passed',reference_span_method='Exact substring in original context; offsets computed locally, original annotated offsets retained.',reference_spans=spans,selection_review='assistant_screened_user_confirmation_pending',review_note='原文支持已核对；现实事实正确性与产品引用真实性需另行判断。'))
        selected.append(dict(task_id=tid,original_data_index=i,original_paragraph_index=j,original_qa=q,context=context))
    suite=dict(suite_id='dureader_robust_dev_5_v1',origin='public_dataset_adapted',description='官方公开开发集5题；目的性筛选的流程验证，不代表完整基准或平台排名。',source_url='https://github.com/baidu/DuReader/tree/master/DuReader-Robust',source_file_sha256=manifest['dev_sha256'],selection_method='固定5个原始ID；覆盖格式、术语、历史、作品、基础概念；非随机抽样',selection_review='assistant_screened_user_confirmation_pending',documents=documents,tasks=tasks)
    dump(output/'tasks.json',suite);dump(output/'sample_review.json',reviews);dump(output/'download_manifest.json',manifest);dump(raw/'selected_samples.json',selected)
    return dict(tasks=len(tasks),output=str(output.resolve()),upload_only=str(materials.resolve()),terms=str((raw/'License.docx').resolve()),product_evaluation='not_run')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output');p.add_argument('--archive');a=p.parse_args();print(json.dumps(prepare(a.output,a.archive),ensure_ascii=False,indent=2))
