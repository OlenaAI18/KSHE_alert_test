"""Export Task 004.4 original-text review workbook and downloadable bundle."""
from pathlib import Path
import csv,json,shutil,zipfile
from export_pattern_discovery_review import sheet_xml

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT.parent/'downloads';DEST.mkdir(exist_ok=True)
REPORT=ROOT/'reports/attribution_experiment_v1'
sheets=[]
for name,file in [('Вікна','pre_alert_window_comparison.csv'),('Перед тривогою','pre_alert_review.csv'),('Усередині тривоги','inside_interval_review.csv')]:
    with (REPORT/file).open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.reader(stream));sheets.append((name,rows))
workbook=DEST/'task0044_attribution_review.xlsx'
with zipfile.ZipFile(workbook,'w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('[Content_Types].xml','<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(sheets)+1))+'</Types>')
    z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i,(name,_) in enumerate(sheets,1))+'</sheets></workbook>')
    z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1))+'</Relationships>')
    for i,(_,rows) in enumerate(sheets,1):z.writestr(f'xl/worksheets/sheet{i}.xml',sheet_xml(rows))
shutil.copy2(REPORT/'attribution_gap_report.md',DEST/'task0044_attribution_report.md')
with zipfile.ZipFile(DEST/'task0044_attribution_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
    for directory in [REPORT,ROOT/'data/processed/attribution_experiment_v1']:
        for p in sorted(directory.glob('*')):z.write(p,p.relative_to(ROOT))
    z.write(workbook,workbook.name)
    z.write(ROOT/'config/threat_dictionary_v1_3.yaml','config/threat_dictionary_v1_3.yaml')
    z.write(ROOT/'config/kyiv_geography_v1_1.yaml','config/kyiv_geography_v1_1.yaml')
print(workbook)
