"""Export Task 004.3 consolidated Parquet and audit review files for download."""
import argparse
import csv
import json
from pathlib import Path
import shutil
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
import zipfile
import pyarrow.parquet as pq
from export_pattern_discovery_review import sheet_xml
from kyiv_alerts.classification.coverage_audit import write_audit_csv


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--output',type=Path,default=Path('/workspace/downloads'))
    args=p.parse_args();report=args.root/'reports/classification_v1_3';data=args.root/'data/processed/classification_v1_3';out=args.output;out.mkdir(parents=True,exist_ok=True)
    r=json.loads((report/'alert_coverage_audit.json').read_text(encoding='utf-8'))
    if r['task_status']!='COMPLETE':raise ValueError('Complete v1.3 coverage audit required')
    g=r['global_metrics'];v=r['version_comparison']
    features=pq.read_table(data/'alert_threat_features.parquet').to_pylist()
    write_audit_csv(features,out/'task0043_alert_features.csv')
    notes=[['Пояснення'],['Task 004.3 — консолідація та аудит покриття; v1.3'],['PROVISIONAL — HUMAN VALIDATION REQUIRED'],
      ['Одиниця аналізу — офіційна тривога. Одна категорія рахується один раз, незалежно від кількості повідомлень.'],
      ['shahed_uav — широка аналітична група БПЛА. Підтип generic_uav не доводить, що конкретна модель була Shahed.'],
      ['jet_uav — явні реактивні БПЛА / моделі та інтерпретований сленг «реактив». inferred_shorthand=true зберігає невпевненість.'],
      [f"Усього {g['total_alerts']} тривоги; {g['eligible_alerts']} придатні; {g['eligible_alerts_with_text']} з текстом; {g['classified_alerts']} з маркерами."],
      [f"Було {v['previous_classified_alerts']}, стало {v['new_classified_alerts']}; нових {v['gained_count']}, втрачено {v['lost_count']}. Це перегрупування наявних маркерів, не підтверджений приріст точності."],
      [f"Категорії крім other: {g['specific_classified_alerts']}; multiple_types: {g['multiple_specific_category_alerts']}; кілька категорій разом з other: {g['multi_label_alerts_including_other']}; only_other: {g['only_other_alerts']}."],
      ['unique_threat_category_count включає other; specific_threat_category_count виключає other. Other разом з одним типом не створює multiple_types.'],
      ['supporting_message_ids і category_message_support — усі прийняті повідомлення в хронологічному порядку. Перший ID не є «причиною тривоги».'],
      ['null — недоступне спостереження; false / 0 — маркер не виявлено у наявному тексті. Це не підтверджена відсутність загрози.'],
      ['28 тривог без маркера: поля human_review_status / human_decision / review_notes порожні. Самостійні місцевості та «ще один» не отримали типу.'],
      ['Дані технічно консолідовані. Аналіз за категоріями потребує незалежної ручної валідації та методики роботи з неповним покриттям. Time Series Analysis не виконувався.']]
    sheets=[('Пояснення',notes)]
    for name,path in [('Тривоги v1.3',out/'task0043_alert_features.csv'),('Порівняння',report/'classification_version_comparison.csv'),('Без маркерів — огляд',report/'unclassified_alerts_review.csv'),('Роки',report/'yearly_coverage.csv'),('Місяці',report/'monthly_coverage.csv')]:
        with path.open(encoding='utf-8-sig',newline='') as stream:sheets.append((name,list(csv.reader(stream))))
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';rels='http://schemas.openxmlformats.org/package/2006/relationships';orel='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    files={'_rels/.rels':f'<Relationships xmlns="{rels}"><Relationship Id="rId1" Type="{orel}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
      'xl/workbook.xml':f'<workbook xmlns="{ns}" xmlns:r="{orel}"><sheets>'+''.join(f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>' for i,(name,_) in enumerate(sheets,1))+'</sheets></workbook>',
      'xl/_rels/workbook.xml.rels':f'<Relationships xmlns="{rels}">'+''.join(f'<Relationship Id="rId{i}" Type="{orel}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1))+f'<Relationship Id="rId{len(sheets)+1}" Type="{orel}/styles" Target="styles.xml"/></Relationships>',
      'xl/styles.xml':f'<styleSheet xmlns="{ns}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf fontId="1" applyFont="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'}
    types='<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    for i,(_,rows) in enumerate(sheets,1):
        files[f'xl/worksheets/sheet{i}.xml']=sheet_xml(rows)
        types+=f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    files['[Content_Types].xml']=types+'</Types>'
    workbook=out/'task0043_alert_review.xlsx'
    with zipfile.ZipFile(workbook,'w',zipfile.ZIP_DEFLATED) as z:
        for name,xml in files.items():ET.fromstring(xml);z.writestr(name,xml)
    with zipfile.ZipFile(workbook) as z:
        assert z.testzip() is None
        for i,(_,rows) in enumerate(sheets,1):assert len(ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml')).find('{'+ns+'}sheetData'))==len(rows)
    shutil.copyfile(report/'alert_coverage_audit.md',out/'task0043_coverage_audit.md')
    for name in ['alert_threat_features','message_threat_markers']:shutil.copyfile(data/(name+'.parquet'),out/('task0043_'+name+'.parquet'))
    with zipfile.ZipFile(out/'task0043_consolidation_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
        for path in [workbook,out/'task0043_alert_features.csv']:z.write(path,path.name)
        for path in sorted(report.glob('*')):
            if path.is_file():z.write(path,'reports/'+path.name)
        for path in sorted(data.glob('*.parquet')):z.write(path,'data/'+path.name)
        z.write(args.root/'config/threat_dictionary_v1_3.yaml','config/threat_dictionary_v1_3.yaml')
        z.write(args.root/'config/kyiv_geography_v1_1.yaml','config/kyiv_geography_v1_1.yaml')
        z.writestr('README.txt','Task 004.3 — dictionary/classification v1.3. PROVISIONAL — HUMAN VALIDATION REQUIRED.\nOne row per official alert; original model evidence and source IDs preserved.\nGeneric UAV != confirmed Shahed model. Inferred reactive shorthand retains uncertainty.\nNo Time Series Analysis was performed.\n')
    print(f'Excel/ZIP verified: {len(sheets)} sheets, {len(features)} unique official alert rows, {r["unclassified_review_sample_size"]} unclassified review alerts.')


if __name__=='__main__':main()
