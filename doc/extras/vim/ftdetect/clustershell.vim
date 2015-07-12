"
" Installed As: vim/ftdetect/clustershell.vim
"
au BufNewFile,BufRead *clush.conf setlocal filetype=clushconf
au BufNewFile,BufRead *groups.conf setlocal filetype=groupsconf
au BufNewFile,BufRead *groups.conf.d/*.conf setlocal filetype=groupsconf
