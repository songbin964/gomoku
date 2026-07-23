# AI五子棋
> 运行方式  
> - 构建gomoku_ai.dll
```
gcc -shared -o gomoku_ai.dll gomoku_ai.c -std=c99 -O2 -lm
```
> - 安装软件包
```
pip install -r requirements.txt
```
> - 然后运行
```
python gomoku.py
```

## 打包
```
pyinstaller gomoku.spec
```