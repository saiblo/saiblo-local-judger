# Saiblo Local Judger (Exp)

实验版的Saiblo本地调试用评测机。

## Overview

1. Core核心：使用TCP Socket提供本地AI连接与游戏运行支持，和Saiblo上的Judger保证行为相同。同时提供了CLI接口。
2. GUI：提供选手易于使用的图形界面
3. AI Adapter：为未支持的AI提供原始协议和TCP协议的转发，但是仍然建议新的游戏的ADK直接提供相关支持

## 核心运行流程

1. 读取提供的游戏配置，其中可能包含
   1. 游戏人数
   2. 游戏逻辑路径
   3. 游戏配置
   4. 通讯协议版本
2. 在随机端口启动本地TCP Socket服务器，并等待AI连接。
3. 全部AI均已成功连接后，启动游戏逻辑
4. 按照 [Saiblo 文档](https://docs.saiblo.net/developer/developer.html) 运行游戏流程
