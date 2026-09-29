# 《Snowmoon（雪月）》中译本 —— 常用命令
#
#   make epub    重新生成 EPUB（成品写在仓库根）
#   make check   校验成品（26 项检查）
#   make all     epub + check
#   make site    本地预览镜像站 http://localhost:8000/
#   make clean   清掉 __pycache__

PY ?= python3

.PHONY: all epub check site clean help

all: epub check

## epub  重新生成 EPUB
epub:
	$(PY) build_epub.py

## check 校验 EPUB
check:
	$(PY) verify_epub.py

## site  本地预览镜像站
site:
	$(PY) -m http.server 8000

## clean 清掉 Python 缓存
clean:
	rm -rf __pycache__ _spec/__pycache__

## help  列出可用目标
help:
	@grep -E "^## " $(MAKEFILE_LIST) | sed "s/^## /  /"
