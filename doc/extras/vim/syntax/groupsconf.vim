
" Vim syntax file for ClusterShell groups.conf

" For version 5.x: Clear all syntax items
" For version 6.x: Quit when a syntax file was already loaded
if version < 600
  syntax clear
elseif exists("b:current_syntax")
  finish
endif

" shut case off
syn case ignore

" Main/default
syn match groupsDefaultValue "\(:\|=\)\s*\w\+$"ms=s+1 contained
syn match groupsColonValue "\(:\|=\).*" contained contains=groupsDefaultValue
syn match groupsDefaultKey "^default\(:\|=\).*$" contains=groupsColonValue
syn match groupsGroupsDirKey "^\(groupsdir\|confdir\|autodir\)\(:\|=\)"

" Sources
syn match groupsVars "\(\$GROUP\|\$NODE\|$SOURCE\)" contained
syn match groupsKeys "^\w\+\(:\|=\)"me=e-1 contained
syn match groupsKeyValue "^\(map\|all\|list\|reverse\|cache_time\)\+\(:\|=\).*$" contains=groupsKeys,groupsVars

syn match  groupsComment    "#.*$"
syn match  groupsComment    ";.*$"
syn match  groupsHeader	    "\[\w\+\(,\w\+\)*\]" contains=gHdrSource,gHdrSourceDelim
syn match  groupsMainHeader "\[Main\]"

syn match  gHdrSource       '[^,]' contained
syn match  gHdrSourceDelim  ',' contained

" Define the default highlighting.
" For version 5.7 and earlier: only when not done already
" For version 5.8 and later: only when an item doesn't have highlighting yet
if version >= 508 || !exists("did_groupsconf_syntax_inits")
  if version < 508
    let did_groupsconf_syntax_inits = 1
    command -nargs=+ HiLink hi link <args>
  else
    command -nargs=+ HiLink hi def link <args>
  endif

  HiLink gHdrSource		Keyword
  HiLink gHdrSourceDelim	Delimiter
  HiLink groupsComment		Comment
  HiLink groupsMainHeader	Constant
  HiLink groupsDefaultKey	Identifier
  HiLink groupsGroupsDirKey	Identifier
  HiLink groupsDefaultValue	Special
  HiLink groupsKeys		Identifier
  HiLink groupsVars		Keyword

  delcommand HiLink
endif

let b:current_syntax = "groupsconf"

" vim:ts=8
