# ngsq2gedcom
Convert an NGSQ formatted genealogy report to a GEDCOM file.

The intention is to capture the family structure of the original data.

Determination of exact names, partners, dates, etc. is very difficult from the free format of the original PDF. The detail content will be inserted into a NOTE field for each individual.

For this parser, the PDF should be converted to CSV via the OCR tools of Amazon AWS Textract in the Layout configuration: https://aws.amazon.com/textract/

At this early stage, read the code for a list of assumptions and conversion notes.

## Notes on variants:
- the document in hand has "b. DATE" after a person's name
- the sample from RMv9 has "was born on DATE"
- the document in hand has a period after the roman numerals for birth order
- the sample from RMv9 does not have a period after the roman numerals
- the document in hand has a line of "Children:" leading the list of children
- the sample from RMv9 uses "...had the following children:"
- the document in hand has "She|He married OTHER"
- the sample from RMv9 has "NAME and OTHER were married"

## Notes on the report format:
- https://web.archive.org/web/20210810080315/http://www.saintclair.org/numbers/nummr.html
- http://higdonfamily.org/research-tips-for-advanced/numbering-systems-for-genea/descending-numbering-system/ngsq-system-1903.html
