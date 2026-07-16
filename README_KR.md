# 💅 Salon De Nature

**언어:** 🇰🇷 한국어 \| 🇺🇸 [English](README.md)

## 네일샵 예약 및 CRM 관리 시스템

Salon De Nature는 실제 소규모 네일샵 운영을 목표로 개발한 **Flask 기반
예약 관리 플랫폼**입니다.

## 주요 기능

-   온라인 예약 / 변경 / 취소
-   고객·관리자 전용 화면
-   고객 CRM 및 세그먼트
-   매출 분석 대시보드
-   REST API(OpenAPI/Swagger)
-   Booking Timeline 및 BookingEvent 이력
-   AWS EC2 + Nginx 배포
-   Google / Kakao OAuth
-   SOLAPI 연동 준비

## 기술 스택

-   Backend: Python, Flask, SQLAlchemy
-   Frontend: HTML, Jinja2, Bootstrap, JavaScript
-   Database: SQLite
-   Infrastructure: AWS EC2, Gunicorn, Nginx

## 시스템 구성

``` text
Browser
  │
Nginx
  │
Gunicorn
  │
Flask
  │
SQLAlchemy
  │
SQLite
```

## 주요 모듈

-   예약 관리
-   고객 CRM
-   매출 분석
-   REST API
-   관리자 대시보드

## REST API

  Method   Endpoint
  -------- ------------------------------------
  GET      /api/v1/services
  GET      /api/v1/staff
  GET      /api/v1/availability
  GET      /api/v1/me/bookings
  POST     /api/v1/me/bookings
  PATCH    /api/v1/admin/bookings/{id}/status

Swagger: - `/api/docs` - `/api/openapi.json`

## 프로젝트 구조

``` text
api/
bookings/
dashboard/
templates/
static/
app.py
config.py
```

## 실행 방법

``` bash
git clone <repository>
cd SalonDeNature_ManagementSystem
python -m venv venv
pip install -r requirements.txt
cp .env.example .env
python app.py
```

## 환경 변수

``` env
SECRET_KEY=
DATABASE_URL=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
KAKAO_CLIENT_ID=
KAKAO_CLIENT_SECRET=
SOLAPI_API_KEY=
SOLAPI_API_SECRET=
SOLAPI_SENDER_NUMBER=
```

## 향후 계획

-   SOLAPI 실발송
-   PostgreSQL
-   Docker
-   GitHub Actions
-   모니터링
