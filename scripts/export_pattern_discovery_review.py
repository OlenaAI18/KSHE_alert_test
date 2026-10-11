"""Create a dependency-free Excel/ZIP review export from Task 004.2 reports."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
import zipfile


def column(index):
    out=''
    while index:index,remainder=divmod(index-1,26);out=chr(65+remainder)+out
    return out


def sheet_xml(rows):
    count=len(rows[0])
    xml=['<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>']
    for i,name in enumerate(rows[0],1):
        width=100 if 'text' in name or 'текст' in name.lower() else 65 if name in {'candidate_interpretation','Пояснення'} else 28
        xml.append(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>')
    xml.append('</cols><sheetData>')
    for index,row in enumerate(rows,1):
        xml.append(f'<row r="{index}">')
        for i,value in enumerate(row,1):
            value=str(value or '')
            if len(value)>32767:raise ValueError('Excel cell exceeds limit; retain full CSV instead')
            xml.append(f'<c r="{column(i)}{index}" t="inlineStr" s="{int(index==1)}"><is><t xml:space="preserve">{escape(value)}</t></is></c>')
        xml.append('</row>')
    xml.append(f'</sheetData><autoFilter ref="A1:{column(count)}{len(rows)}"/></worksheet>')
    return ''.join(xml)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--output',type=Path,default=Path('/workspace/downloads'))
    args=p.parse_args();report=args.root/'reports/pattern_discovery';out=args.output;out.mkdir(parents=True,exist_ok=True)
    r=json.loads((report/'pattern_discovery_report.json').read_text(encoding='utf-8'))
    if r['task_status']!='TECHNICALLY COMPLETE':raise ValueError('Discovery report must be technically complete')
    b=r['baseline'];o=r['october']
    notes=[['Пояснення'],['Task 004.2 — кандидати патернів для ручного перегляду'],['Словники та класифікація не змінені. Жодні нові категорії не схвалені автоматично.'],
      [f"База: {b['total_alerts']} офіційні тривоги; {b['eligible_alerts']} придатні; {b['eligible_alerts_with_text']} з текстом; {b['classified_alerts']} класифіковані."],
      [f"A — конкретні категорії: {b['populations']['specific_classified']}; B — лише other: {b['populations']['other_only']}; C — текст без класифікації: {b['populations']['text_unclassified']}; D — недоступні/невизначені: {b['populations']['unavailable_or_unresolved']}."],
      [f"Жовтень: {o['total_alerts']} тривоги, {o['alerts_with_text']} з текстом; 0 з конкретним типом; 1 лише other; {o['linked_text_messages']} текстових повідомлень."],
      [f"Останній початок офіційної тривоги: {r['official_last_start_kyiv']}; кінець: {r['official_last_end_kyiv']}. Telegram до {r['source_last_timestamp_kyiv']}. Жовтень неповний."],
      ['Підтримка патерна — унікальні тривоги B/C. Патерни перетинаються: не підсумовуйте їхні числа.'],
      ['P01/P03/P04/P09 та інші короткі фрагменти потребують контекстної перевірки. Назва місцевості або рух не доводять тип об’єкта.'],
      ['P16/P17 показують відхилені маркери; деякі виключення правильні (область, інші регіони, скасування, історичні згадки).'],
      ['Рекомендовані дії є гіпотезами. human_decision, review_status та review_notes залишені порожніми.'],
      [f"Лексичні кандидати зустрічаються в {r['exploratory_potential']['lexical_review_upper_bound_alerts']} некласифікованих тривогах; лише {r['exploratory_potential']['lexical_review_with_literal_city_upper_bound_alerts']} мають у тому самому повідомленні словникову географію Києва. Це межа черги перевірки, не підтверджене покращення."],
      ['Повні оригінальні повідомлення та часові мітки збережені. Для великих таблиць і частот відкрийте CSV з ZIP-архіву.']]
    sheets=[('Пояснення',notes)]
    tables=[('Патерни','candidate_patterns.csv'),('Жовтень — тривоги','october_2026_alert_review.csv'),('Періоди','period_comparison.csv'),('Приклади','representative_examples.csv'),('Жовтень — повідомлення','october_2026_messages.csv')]
    for name,file in tables:
        with (report/file).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.reader(f))
        sheets.append((name,rows))
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
    workbook=out/'task0042_pattern_review.xlsx'
    with zipfile.ZipFile(workbook,'w',zipfile.ZIP_DEFLATED) as z:
        for name,xml in files.items():ET.fromstring(xml);z.writestr(name,xml)
    with zipfile.ZipFile(workbook) as z:
        assert z.testzip() is None
        for i,(_,rows) in enumerate(sheets,1):assert len(ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml')).find('{'+ns+'}sheetData'))==len(rows)
    shutil.copyfile(report/'pattern_discovery_report.md',out/'task0042_pattern_report.md')
    shutil.copyfile(report/'candidate_patterns.csv',out/'task0042_candidate_patterns.csv')
    with zipfile.ZipFile(out/'task0042_pattern_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
        z.write(workbook,workbook.name)
        for path in sorted(report.glob('*')):
            if path.is_file():z.write(path,'reports/'+path.name)
        z.write(args.root/'requirements-analysis.lock.txt','requirements-analysis.lock.txt')
        for path in sorted((args.root/'src/kyiv_alerts/pattern_discovery').glob('*.py')):z.write(path,'code/'+path.name)
        z.writestr('README.txt','Task 004.2: read-only exploratory diagnostics. Review Excel/CSV; human labels remain blank.\nReproduce within existing repository:\n.venv/bin/python -m pip install -r requirements-analysis.lock.txt\n.venv/bin/python -m kyiv_alerts.pattern_discovery\nNo dictionary/classification changes were made.\n')
    print(f'Excel/ZIP verified: {len(sheets)} sheets, {len(r["candidate_patterns"])} families, {o["total_alerts"]} October alerts.')


if __name__=='__main__':main()
