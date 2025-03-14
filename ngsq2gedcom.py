"""
Convert am NGSQ report genealogy NGSQ report file into a GEDCOM file
provided the PDF report has been OCRed into a CSV using Amazon AWS Textract in Layout configuration.

This code is released under the MIT License: https://opensource.org/licenses/MIT
Copyright (c) 2025 John A. Andrea

No support provided.

v0.6.2
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
#- no consideration for multiple marriages or children thereof

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
# 1/  given middle surname #123, details
ross_numbered = re.compile( '([^#]+) #(\\d+)[,|\\.]?(.*)' )

# more attempt to extract the name
# in order of checking
# use non-greedy match for name section
# 2/  first middle surname. b. date...
# 3/  first middle surname, b. date...
# 4/  first middle surname b. date...
# 5/  first middle surname. b. Abt date...
# 6/  first middle surname, b. Abt date...
# 7/  first middle surname b. Abt date...
# also use died "d. " but check on born first
# also use "bef date" and "aft date"
# 8 like 2,3,4 but month with no day
# 9/  name. She|He married...
# 10/ name. Single....
# 11/ name. town in year...
# 12/ name. town when father died...
# x/ name. town-name...

name_matchers = []
name_matchers.append( re.compile( '^(.*?)[,|\\.]? (b\\. \\d+ .*)' ) ) #2, 3, 4
name_matchers.append( re.compile( '^(.*?)[,|\\.]? (b\\. [A|a]bt .*)' ) ) #5, 6, 7
name_matchers.append( re.compile( '^(.*?)[,|\\.]? (b\\. [B|b]ef .*)' ) ) #5, 6, 7 + bef
name_matchers.append( re.compile( '^(.*?)[,|\\.]? (b\\. [A|a]ft .*)' ) ) #5, 6, 7 + aft
name_matchers.append( re.compile( '^(.*?)[,|\\.]? (d\\. \\d+ .*)' ) ) #2, 3, 4 dief
name_matchers.append( re.compile( '^(.*?)[,|\\.]? (d\\. [A|a]bt .*)' ) ) #5, 6, 7 died
name_matchers.append( re.compile( '^(.*?)[,|\\.]? (d\\. [B|b]ef .*)' ) ) #5, 6, 7 died + bef
name_matchers.append( re.compile( '^(.*?)[,|\\.]? (d\\. [A|a]ft .*)' ) ) #5, 6, 7 died + aft
name_matchers.append( re.compile( '^(.*?)[,|\\.]? (b\\. [A-Z][a-z][a-z] \\d.*)' ) ) #8
name_matchers.append( re.compile( '^(.*?)[,|\\.]? (d\\. [A-Z][a-z][a-z] \\d.*)' ) ) #8 died
name_matchers.append( re.compile( '^(.*?)\\. (S?[H|h]e married.*)' ) ) #9
name_matchers.append( re.compile( '^(.*?)\\. (Single\\..*)' ) ) #10
name_matchers.append( re.compile( '^(.*?)\\. ([A-Za-z, ]+? in \\d\\d\\d\\d.*)' ) ) #11
name_matchers.append( re.compile( '^(.*?)\\. ([A-Za-z, ]+? when father died)' ) ) #12

# short; as in no detail portion
name_matchers_short = []
name_matchers_short.append( re.compile( '^([\\w\\(\\) ]+)\\.$' ) )

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

# need to backtrack when OCR separates numbers and roman numerals from name lines
# example
# + 10
# 11
# vii. NAME10.
# + 12
# viii. NAME11, b. 17 Jul
# 13
# ix. NAME12 b. Abt 1927.
# X. NAME13, b. Abt 1933 in
# Oh, this is a mess. Maybe detect the problem and fail with message.
# Handle these cases and ignore the one where a break is after the roman numerals.
backtrack = []

#bare_parent_number = re.compile( '^(\\d+)\\.$' )
broken_lines = []
broken_lines.append([ 'bare child plus', re.compile( '^(\\+)$') ])
broken_lines.append([ 'bare child number', re.compile( '^(\\d+)$') ])
broken_lines.append([ 'bare child plus and number', re.compile( '^(\\+ ?\\d+)$' ) ])
broken_lines.append([ 'bare child roman and name', re.compile( '^([i|I|v|V|x|X]+\\. ?...*)$' ) ])

# name of a backtracked line to stop looking
backtrack_end = 'done'

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


def extract_name( given ):
    print( '', file=sys.stderr ) #debug
    print( 'try name/', given, file=sys.stderr ) #debug

    name = ''
    after = ''

    for name_match in name_matchers:
        m = name_match.match( given )
        if m:
           name = m.group(1)
           after = m.group(2)
           break
    if not name:
       # consider running this loop a second time to pick through multiple phrases
       for name_match in name_matchers_short:
           m = name_match.match( given )
           if m:
              name = m.group(1)
              break
    if not name:
       name = given
       after = given

    print( 'got name/', name, file=sys.stderr ) #debug
    return [ name, after ]


def start_child( p, remainder_of_line ):
    # inputs should have been 'strip()ed'
    # if the person was picked up as a child and is now a parent,
    #    replace these items
    results = dict()
    results['name'] = ''
    results['sex'] = ''
    results['rossid'] = ''
    results['lines'] = []
    results['children'] = []
    results['famc'] = None
    # this person might not have any children, but setup a family number
    # equal to person number
    results['fams'] = p

    # try to extract the name portion
    name = ''
    ross_id = ''
    after_name = ''
    m = ross_numbered.match( remainder_of_line )
    if m:
       # (1)
       name = m.group(1)
       ross_id = m.group(2)
       after_name = m.group(3)
    else:
       name_parts = extract_name( remainder_of_line )
       name = name_parts[0]
       after_name = name_parts[1]

    results['name'] = name.strip()
    results['rossid'] = ross_id.strip()
    results['lines'].append( after_name.strip() )

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

        # might not have any children,
        # but family record usable if children or in marriage
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


def broken_recovery():
    global backtrack
    global people

    print( '', file=sys.stderr ) #debug
    print( 'recover backtrack: show all lines', file=sys.stderr ) #debug
    for line in backtrack:
        print( line, file=sys.stderr ) #debug

    # broken being handled
    # ignoring when a break is after a roman number
    # 1/ bare child plus/            +        -> 2
    # 2/ bare child number/          nn       -> 4
    # 3/ bare child plus and number/ +nn      -> 4
    # 4/ bare child roman and name/  xvi. name-> done

    #print( 'recover backtrack: actions', file=sys.stderr ) #debug
    next_matches = dict()
    #1
    next_matches['bare child plus'] = ['bare child number']
    #2
    next_matches['bare child number'] = ['bare child roman and name']
    #3
    next_matches['bare child plus and number'] = ['bare child roman and name']
    #4
    next_matches['bare child roman and name'] = [backtrack_end]

    fixed_line = ''
    for index, line in enumerate(backtrack):
        name = line['name']
        if name:
           # turn off this line
           backtrack[index]['name'] = ''
           # collect this content
           fixed_line = line['value']
           # what to look for next
           find_next = next_matches[name]

           found_matchup = False
           found_end = False
           early_exit = False
           while not found_end and not early_exit:
               for next_index, next_line in enumerate(backtrack):
                   next_name = next_line['name']
                   if next_name in find_next:
                      #print( 'matched up/', line['value'], '/with/', next_line['value'], file=sys.stderr ) #debug
                      found_matchup = True
                      # collect this content
                      fixed_line += ' ' + next_line['value']
                      # unusable now that its been collected
                      backtrack[next_index]['name'] = ''
                      # next part to search for
                      find_next = next_matches[next_name]
                      #print( 'recovered/', fixed_line, file=sys.stderr ) #debug
                      #print( 'looking for/', find_next, file=sys.stderr ) #debug
                      if backtrack_end in find_next:
                         found_end = True
                      break
               if not found_matchup:
                  early_exit = True
                  print( 'didnt match/', line['value'], '/index', index, file=sys.stderr ) #debug

           print( 'recovered/', fixed_line, file=sys.stderr ) #debug
               #print( 'EXITING for debug', file=sys.stderr ) #debug
               #sys.exit() #debug

    # all done, erase the saved lines
    backtrack = []


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
            if backtrack:
               broken_recovery()
            # 123. name-part detail-part
            in_children = False
            person_n = m.group(1).strip()
            remainder = m.group(2).strip()
            #print( 'parent', person_n, content, file=sys.stderr ) #debug
            # check for ocr mistake at the end of any line in a parent
            if content.endswith( ' Children:' ):
               in_children = True
            if first_person is None:
               first_person = person_n
               # only the first person is like a child because of no parents
               people[person_n] = start_child( person_n, remainder )
            else:
               # every, except first, parent should already have been seen
               # so just add the line part, though this will include name
               people[person_n]['lines'].append( remainder )
            current_parent = person_n
            current_person = person_n
            continue

         if in_children:
            #print( 'in children', file=sys.stderr ) #debug
            m = child_marker.match( content )
            if m:
               if backtrack:
                  broken_recovery()
               # +123 vii. name-part detail-part
               # or
               # 123 vii. name-part detail-part
               person_n = m.group(2).strip()
               remainder = m.group(3).strip()
               #print( 'child', person_n, content, file=sys.stderr ) #debug
               # this child might become a parent later
               people[person_n] = start_child( person_n, remainder )
               current_person = person_n
               # parent family includes this child
               people[current_parent]['children'].append( person_n )
               # belong to parent family
               people[person_n]['famc'] = people[current_parent]['fams']
               continue
         else:
            # check for ocr mistake at the end of any line in a parent
            if content.endswith( ' Children:' ):
               in_children = True

         broken_reason = ''
         for check_broken in broken_lines:
             m = check_broken[1].match( content )
             if m:
                broken_reason = check_broken[0]
                #print( 'WARN broken line/', broken_reason, '/', content, file=sys.stderr ) #debug
         if broken_reason:
            backtrack.append( {'name':broken_reason, 'value':content} )
         else:
            # otherwise: attach to the the current person,
            # but skip the header section until the first person is found
            if first_person is not None:
               people[current_person]['lines'].append( content )
               print( 'attach to person/', current_person, '/', content, file=sys.stderr )

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
