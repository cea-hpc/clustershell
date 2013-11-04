
" Vim syntax file for clush.conf

" For version 5.x: Clear all syntax items
" For version 6.x: Quit when a syntax file was already loaded
if version < 600
  syntax clear
elseif exists("b:current_syntax")
  finish
endif

" shut case off
syn case ignore

syn match  clushComment	    "#.*$"
syn match  clushComment	    ";.*$"
syn match  clushHeader	    "\[\w\+\]"

syn keyword clushKeys       fanout command_timeout connect_timeout color fd_max history_size node_count verbosity
syn keyword clushKeys       ssh_user ssh_path ssh_options
syn keyword clushKeys       rsh_path rcp_path rcp_options

" Define the default highlighting.
" For version 5.7 and earlier: only when not done already
" For version 5.8 and later: only when an item doesn't have highlighting yet
if version >= 508 || !exists("did_clushconf_syntax_inits")
  if version < 508
    let did_clushconf_syntax_inits = 1
    command -nargs=+ HiLink hi link <args>
  else
    command -nargs=+ HiLink hi def link <args>
  endif

  HiLink clushHeader	Special
  HiLink clushComment	Comment
  HiLink clushLabel	Type
  HiLink clushKeys      Identifier

  delcommand HiLink
endif

let b:current_syntax = "clushconf"

" vim:ts=8
