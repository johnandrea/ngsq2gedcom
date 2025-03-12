# ngsq2gedcom
Convert an NGSQ formatted genealogy report to a GEDCOM file.

The intention is to capture the family structure of the original data. Determination of exact names, partners, dates, etc. is very difficult from the free format of the original PDF.

For this parser the PDF should be converted to CSV via the OCR tools of Amazon AWS Textract in the Layout configuration: https://aws.amazon.com/textract/

At this early stage, read the code for a list of assumptions and conversion notes.

## Notes on the report format:
- https://web.archive.org/web/20210810080315/http://www.saintclair.org/numbers/nummr.html
- http://higdonfamily.org/research-tips-for-advanced/numbering-systems-for-genea/descending-numbering-system/ngsq-system-1903.html
