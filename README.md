# 💅 Salon De Nature

### Production-ready Nail Salon Reservation & CRM Management System

> A full-stack reservation platform built with **Flask**, designed for
> real salon operations. It includes online reservations, CRM,
> analytics, REST API, AWS deployment, and operational workflows.

------------------------------------------------------------------------

# Preview

> Replace the placeholders below with screenshots.

  Main                        Reservation
  --------------------------- ----------------------------------
  ![](docs/images/main.png)   ![](docs/images/reservation.png)

  CRM                        Revenue Dashboard
  -------------------------- ------------------------------
  ![](docs/images/crm.png)   ![](docs/images/revenue.png)

  Admin Calendar                  Swagger
  ------------------------------- ------------------------------
  ![](docs/images/calendar.png)   ![](docs/images/swagger.png)

------------------------------------------------------------------------

# Project Goals

This project was built to simulate the complete workflow of a small nail
salon.

It focuses on:

-   Customer self-service reservation
-   Administrator reservation management
-   Customer CRM
-   Revenue analytics
-   REST API
-   AWS production deployment

------------------------------------------------------------------------

# Key Features

## Customer

-   Online reservation
-   Reschedule & cancellation
-   Google OAuth
-   Kakao OAuth
-   Reservation timeline
-   My Booking

## Administration

-   Reservation calendar
-   Timeline view
-   Staff management
-   Business hours / holidays
-   Booking status workflow
-   BookingEvent history

## CRM

-   Customer analytics
-   Customer segmentation
-   VIP / Returning / Potential VIP / Dormant / At Risk
-   Customer notes
-   Favorite services
-   Favorite staff

## Analytics

-   Revenue dashboard
-   KPI cards
-   Revenue by staff
-   Revenue by service
-   Booking trends
-   Reservation status analysis

## REST API

-   Customer API
-   Admin API
-   Swagger / OpenAPI
-   CSRF protection
-   Rate limiting
-   CORS
-   Request logging

------------------------------------------------------------------------

# Technology Stack

  Category         Stack
  ---------------- --------------------------------------
  Backend          Python, Flask, SQLAlchemy
  Database         SQLite
  Frontend         HTML5, Jinja2, Bootstrap, JavaScript
  Deployment       AWS EC2, Gunicorn, Nginx, systemd
  Authentication   Google OAuth, Kakao OAuth
  External         SOLAPI (SMS)

------------------------------------------------------------------------

# Architecture

``` text
Browser
   │
   ▼
Nginx
   │
   ▼
Gunicorn
   │
   ▼
Flask
   │
   ▼
SQLAlchemy
   │
   ▼
SQLite
```

> Replace this section later with your draw.io architecture diagram.

------------------------------------------------------------------------

# Database

Insert your ERD here.

``` text
Customer
 ├── Booking
 │     └── BookingEvent
 ├── Service
 ├── Staff
 ├── SMSLog
 └── Revenue
```

------------------------------------------------------------------------

# REST API

  Method   Endpoint                               Description
  -------- -------------------------------------- ----------------------
  GET      `/api/v1/health`                       Health check
  GET      `/api/v1/services`                     Service list
  GET      `/api/v1/staff`                        Staff list
  GET      `/api/v1/availability`                 Available time slots
  GET      `/api/v1/me/bookings`                  Customer bookings
  POST     `/api/v1/me/bookings`                  Create booking
  POST     `/api/v1/me/bookings/{id}/cancel`      Cancel booking
  PATCH    `/api/v1/admin/bookings/{id}/status`   Change status
  GET      `/api/v1/admin/analytics/revenue`      Revenue analytics

Swagger: - `/api/docs` - `/api/openapi.json`

------------------------------------------------------------------------

# Folder Structure

``` text
api/
bookings/
dashboard/
static/
templates/
app.py
config.py
models.py
requirements.txt
```

------------------------------------------------------------------------

# Security

-   Session authentication
-   CSRF protection
-   Role-based authorization
-   Booking ownership validation
-   Rate limiting
-   CORS
-   HTTPS deployment

------------------------------------------------------------------------

# Local Setup

``` bash
git clone <repository>
cd SalonDeNature_ManagementSystem

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env

python app.py
```

------------------------------------------------------------------------

# Environment Variables

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

------------------------------------------------------------------------

# Deployment

-   AWS EC2
-   Gunicorn
-   Nginx
-   Let's Encrypt HTTPS
-   systemd

------------------------------------------------------------------------

# Development Timeline

-   Reservation System
-   Admin Dashboard
-   Revenue Analytics
-   CRM
-   REST API
-   Production Deployment

------------------------------------------------------------------------

# Future Roadmap

-   SOLAPI production activation
-   PostgreSQL
-   Docker
-   GitHub Actions
-   Monitoring

------------------------------------------------------------------------

# License

Portfolio / Educational Project
