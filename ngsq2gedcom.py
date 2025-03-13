"""
Convert am NGSQ report genealogy NGSQ report file into a GEDCOM file
provided the PDF report has been OCRed into a CSV using Amazon AWS Textract in Layout configuration.

This code is released under the MIT License: https://opensource.org/licenses/MIT
Copyright (c) 2025 John A. Andrea

No support provided.

v0.1
"""

import sys
import os
import re
import csv

# Assumptions and notes:
#- output to stdout
#- parameter: name of directory containing input file "layout.csv"
#- no consideration of special (non-ansi) characters
#- children lines all include roman numeral birth orders
#- sometimes the ocr messes up the location of the start children line
#- surnames are the last word of a name portion (probebly wrong to assume)
#- lines are processed in a state machine style
#- sex is determined my the phrase in the notes and common first names
#- a person without a sex will be listed as HUSB in a family record
#- INDI XREF values are taken from person numbers in the input

# This particular version parses a document whic has "#numbers" following
# the name (most of them) which becomes a REFN tag.


## marker for debug info
#mark = ''
#unmark = '>>'

# mark of a new person (but not inside child block)
# ^ digits dot
person_marker = re.compile( '^(\\d+)\\. (.*)' )

# mark of a child name line
# ^ optional plus sign space digits space roman-numerals dot space
# some of the spaces in there are optional
child_marker = re.compile( '^(\\+)? ?(\\d+) [i|I|v|V|x|X]+\\. ?(.*)' )

# line with name might contain the Ross MacKay id number
# name-chars # digits comma|dot chars
ross_numbered = re.compile( '([^#]+) #(\\d+)[,|\\.]?(.*)' )

# inside a children block
in_children = False

# csv columns by name
col_names = dict()

# at beginning
first_person = None

# to match with children
current_parent = None

# to match lines to person
current_person = None

# the data
# this will be global
people = dict()

# defined in the spec for v5.5.1
# this is for the line, subtract len( '2 note ' ) = 7, plus 2 for good luck
note_limit = 246

# defined in the spec
# but both the givn and surn are each allowed to have that same length\
# subtract len( '1 name //' ) = 9 , plus 2
name_limit = 110

# common names to help determine sex
# note, all lowercase
females = ['adele', 'alice', 'amelia', 'andrea', 'ann', 'annie', 'antoinette',
           'aurora', 'barbara', 'bernice', 'carol', 'catherine', 'cecilia',
           'cynthia', 'daphne', 'denise', 'donna', 'elizabeth', 'emily', 'esme',
           'esther', 'eugenia', 'eva', 'evelyn', 'farrah', 'gail', 'geneva',
           'genevieve', 'genie', 'hazel', 'helen', 'hindth', 'irene', 'isabelle',
           'jamalie', 'jane', 'janet', 'jean', 'joan', 'josephine', 'joyce', 'julia',
           'julie', 'juliet', 'juliette', 'karen', 'katherine', 'kyla', 'lillian',
           'linda', 'loretta', 'lorraine', 'louise', 'lulu', 'lynn', 'madeline',
           'mamie', 'margaret', 'marguerite', 'maria', 'mariam', 'marie', 'marina',
           'marion', 'martha', 'mary', 'matilda', 'mercedes', 'meriana', 'minera',
           'morena', 'nancy', 'odette', 'patricia', 'paula', 'paulette', 'rebecca',
           'regina', 'rita', 'roberta', 'rochelle', 'rosa', 'rose', 'sadie', 'sandra',
           'sarah', 'sarrauff', 'serena', 'sevilla', 'shaheedy', 'shela', 'shirley',
           'sister', 'suraya', 'susan', 'suzette', 'sylvia', 'theresa', 'thresa',
           'veronica', 'victoria', 'virginia', 'yamile', 'yvonne']
males = ['abdullah', 'abraham', 'adrian', 'albert', 'allan', 'alsyus', 'anthony',
         'antonio', 'badaoui', 'boutrous', 'brent', 'brian', 'cameron', 'charles',
         'chester', 'christopher', 'daniel', 'dave', 'david', 'derek', 'edward',
         'elias', 'eugene', 'felix', 'francis', 'frank', 'fred', 'frederick',
         'gabriel', 'garth', 'gary', 'george', 'gerald', 'gordon', 'haid', 'harold',
         'james', 'jerges', 'jerry', 'john', 'jorge', 'joseph', 'kevin', 'khalil',
         'louis', 'male', 'marshall', 'maurice', 'michael', 'nahman', 'paul', 'peter',
         'philip', 'pierre', 'rafoul', 'randolph', 'raymond', 'rev.', 'richard',
         'rob', 'robert', 'roger', 'ronald', 'ronnie', 'roy', 'salim', 'salomon',
         'simon', 'stephan', 'tannous', 'thomas', 'tony', 'vincent', 'wadih',
         'william', 'youssef']


def gedcom_header():
    print( '''0 HEAD
1 SOUR ProgramGenerated
1 SUBM @S1@
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
0 @S1@ SUBM
1 NAME John Andrea''' )

def gedcom_trailer():
    print( '0 TRLR' )


def unquote_row( row_data ):
    # the aws fields have leading single quote
    # probably to ensure spreadsheets use the fields as strings
    # remove that quote
    output = []
    for r in row_data:
        if r.startswith( "'" ):
           r = r[1:]
        output.append( r.strip() )
    return output


def start_person( p, remainder_of_line ):
    results = dict()
    results['name'] = ''
    results['sex'] = ''
    results['rossid'] = ''
    results['lines'] = []
    results['children'] = []
    # this person might not have any children, but setup a family number
    results['fams'] = p
    results['famc'] = None

    # try to extract the name portion
    m = ross_numbered.match( remainder_of_line )
    if m:
       name = m.group(1)
       ross_id = m.group(2)
       after_name = m.group(3)

       results['name'] = name
       results['rossid'] = ross_id
       results['lines'].append( after_name )
    else:
       results['name'] = remainder_of_line
       results['lines'].append( remainder_of_line )

    return results


def show_people( indent, p ):
    print( indent + '>', p, file=sys.stderr )
    print( indent + people[p]['name'], file=sys.stderr )
    if not people[p]['name']:
       print( indent, '!!! no name', file=sys.stderr ) #debug
    print( indent + 'sex', people[p]['sex'], file=sys.stderr )
    print( indent + 'rossid', people[p]['rossid'], file=sys.stderr )
    n = 0
    for line in people[p]['lines']:
        n += 1
        print( indent + 'line', n, line, file=sys.stderr )
    for child in people[p]['children']:
        show_people( indent + '   ', child )


def gedcom_indi( p ):
    print( '0 @I' + p + '@ INDI' )
    print( '1 NAME', people[p]['name'] )
    print( '2 GIVN',  people[p]['givn'] )
    print( '2 SURN',  people[p]['surn'] )
    if people[p]['notes']:
       size = len( people[p]['notes'] )
       prefix = '1 NOTE'
       if size <= note_limit:
          print( prefix, people[p]['notes'] )
       else:
          output = ''
          n = 0
          for i in range( size ):
              if n == note_limit:
                 print( prefix, output )
                 prefix = '2 CONT'
                 output = ''
                 n = 0

              output += people[p]['notes'][i]
              n += 1
          # final chars
          print( prefix, output )

    if people[p]['rossid']:
       print( '1 REFN', people[p]['rossid'] )
    if people[p]['sex']:
       print( '1 SEX', people[p]['sex'] )
    # only this first person won't be a child
    if people[p]['famc'] is not None:
       print( '1 FAMC @F' + people[p]['famc'] + '@' )
    if people[p]['in-fams']:
       print( '1 FAMS @F' + people[p]['fams'] + '@' )

    for child in people[p]['children']:
        gedcom_indi( child )


def gedcom_fam():
    for p in people:
        if people[p]['in-fams']:
           print( '0 @F' + people[p]['fams'] + '@ FAM' )
           sex = people[p]['sex']
           if sex == 'F':
              print( '1 WIFE @I' + p + '@' )
           else:
              # if unknown, assume husb and fix later
              print( '1 HUSB @I' + p + '@' )

           for child in people[p]['children']:
               print( '1 CHIL @I' + child + '@' )


def process_people():
    # define sex, note, etc.
    for p in people:
        whole_note = ''
        for line in people[p]['lines']:
            whole_note += ' ' + line
        people[p]['notes'] = whole_note.replace( '  ', ' ' ).replace( '  ', ' ' ).strip()

        # might not have any children, but if married then in a family
        in_fams = len(people[p]['children']) > 0
        sex = ''
        if 'He married' in people[p]['notes']:
           sex = 'M'
           in_fams = True
        if 'She married' in people[p]['notes']:
           sex = 'F'
           in_fams = True
        if not sex:
           # compare the first name to the lists of common names
           first_name = people[p]['name'].split()[0].lower()
           if first_name in males:
              sex = 'M'
           elif first_name in females:
              sex = 'F'
        people[p]['sex'] = sex

        people[p]['in-fams'] = in_fams

        # limit name size
        name_parts = people[p]['name'].replace('Dr. ','').replace('Rev. ','').split()
        # instead - do this on the individual parts
        #if len( name ) > name_limit:
        #   people[p]['name'] = name[:name_limit-1]
        given = ' '.join( name_parts[:len(name_parts)-1] )
        surname = name_parts[-1]
        people[p]['givn'] = given[:name_limit-1].strip()
        people[p]['surn'] = surname[:name_limit-1].strip()
        people[p]['name'] = people[p]['givn'] + ' /' + people[p]['surn'] + '/'


with open( sys.argv[1] + os.path.sep + 'layout.csv', encoding="utf-8" ) as inf:
     csvreader = csv.reader( inf )

     # first line
     fields = unquote_row( next( csvreader ) )

     n = 0
     for f in fields:
         col_names[f.lower()] = n
         n += 1

     for row in csvreader:
         data = unquote_row( row )
         layout = data[col_names['layout']].lower()
         if layout.startswith( 'title' ):
            continue
         if layout.startswith( 'page number' ):
            continue
         if layout.startswith( 'section header' ):
            continue

         content = data[col_names['text']]
         if not content:
            continue
            # sometimes not detected as a section header
         if content.startswith( 'Generation ' ):
            continue

         if content == 'Children:':
            #print( mark, 'in chidren', file=sys.stderr )
            in_children = True
            continue

         m = person_marker.match( content )
         if m:
            in_children = False
            person_n = m.group(1)
            remainder = m.group(2)
            #print( mark, 'person number/', person_n, file=sys.stderr )
            people[person_n] = start_person( person_n, remainder )
            # check for ocr mistake
            if remainder.endswith( ' Children:' ):
               in_children = True
            if first_person is None:
               first_person = person_n
            current_parent = person_n
            current_person = person_n
            continue

         if in_children:
            m = child_marker.match( content )
            if m:
               person_n = m.group(2)
               remainder = m.group(3)
               people[person_n] = start_person( person_n, remainder )
               current_person = person_n
               # parent family includes this child
               people[current_parent]['children'].append( person_n )
               # belong to parent family
               people[person_n]['famc'] = people[current_parent]['fams']
               continue

         if first_person is not None:
            people[current_person]['lines'].append( content )
         #print( unmark, content, file=sys.stderr )

if first_person is None:
   print( 'problem: no one detected', file=sys.stderr )
else:
   process_people()
   #print( '', file=sys.stderr )
   #print( 'People', file=sys.stderr )
   #show_people( '', first_person )

   gedcom_header()
   gedcom_indi( first_person )
   gedcom_fam()
   gedcom_trailer()
