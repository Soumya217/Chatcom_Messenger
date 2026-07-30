# Chatcom_Messenger
Full-stack real-time messaging platform (Chatcom Messenger) with an admin analytics dashboard tracking DAU, message volume, most active users, and a 7-day engagement forecast.
# Chatcom Messenger — Data Analytics Module

## Overview
Chatcom Messenger is a full-stack, real-time chat platform supporting 1-to-1 and 
group messaging, built as part of a Full Stack Development internship (Week 6 Final 
Task). This repository contains my individual submission for the **Data Analytics** 
role task: an admin-facing analytics dashboard that turns raw chat activity into 
actionable engagement insights.

## What this project does
- Simulates a working chat app (Flask + Socket.IO + SQLite) to generate realistic, 
  time-stamped user and message data — since building this on top of a live 
  production messenger wasn't required for the analytics role specifically.
- Extracts that data and visualizes it in Power BI, covering every requirement 
  from the brief: an analytics dashboard, Daily Active Users, Messages Sent per 
  Day, Most Active Users, and — as a bonus — a predictive engagement trend 
  forecast using time-series forecasting.
- Surfaces the findings as written insights and recommendations, not just charts, 
  so the numbers translate into decisions an admin could actually act on.

## Tech stack
- **Data generation**: Python, Flask, Flask-SocketIO, SQLite (run via Google Colab)
- **Analysis & visualization**: Power BI (DAX measures, forecasting, custom visuals)
- **Data pipeline**: pandas, SQLite exports → CSV → Power BI

## Key findings
- 100% user activation — every registered user sent at least one message
- Balanced usage across all three chat spaces (no single feature dominates)
- Clear weekly engagement cycle (weekday peaks, weekend dips)
- 7-day forecast shows a stable engagement plateau rather than decline or 
  explosive growth

See `data-analytics/insights.md` for the full write-up.
