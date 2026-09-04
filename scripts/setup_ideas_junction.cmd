@echo off
rem Make ideas/ a junction to zenn-content/ideas (private memos live there; ideas/ is gitignored here).
rem Keep this file ASCII-only and free of parenthesized blocks: cmd.exe misparses UTF-8 text and LF-only blocks.
if exist "C:\Users\81909\dev\zenn-trend\ideas" echo ideas already exists && exit /b 0
mklink /J "C:\Users\81909\dev\zenn-trend\ideas" "C:\Users\81909\dev\zenn-content\ideas"
