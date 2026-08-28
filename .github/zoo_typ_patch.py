from pathlib import Path
p = Path('styles/uralla.txt')
s = p.read_text(encoding='utf-8')
anchor = '[_point]\nType=0x02c\nSubType=0x08\n'
assert 'Type=0x02c\nSubType=0x07\n' not in s
assert s.count(anchor) == 1
block = '''[_point]
Type=0x02c
SubType=0x07
;GRMN_TYPE: Business - Attractions/ZOO/Zoo/Non NT
String1=0x19,зоопарк
String2=0x04,zoo
ExtendedLabels=Y
FontStyle=SmallFont
CustomColor=No
ContourColor=No
DayXpm="14 14 3 1"   Colormode=16
"!\tc #000000"
"#\tc #FFFFFF"
" \tc none"
"    !!!!      "
"   !####!     "
"  !######!    "
" !##!##!##!   "
" !########!   "
"  !######!    "
"   !####!     "
"    !!!!      "
"   !!  !!     "
"  !!    !!    "
" !!      !!   "
"!!        !!  "
"            ! "
"              "
;12345678901234
[end]


'''
p.write_text(s.replace(anchor, block + anchor, 1), encoding='utf-8')
