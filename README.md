# 📊 BizSight

### AI-Powered Business Analytics Platform for SMEs & E-Commerce Businesses

**BizSight** is a business analytics application designed to help **Small and Medium Enterprises (SMEs), e-commerce businesses, and online businesses** understand their sales and financial data without requiring advanced data-analysis skills.

The application allows users to upload their business data, automatically processes and cleans it, performs financial and statistical analysis, generates meaningful business insights, and presents the results through an interactive dashboard.

---

## 🚀 What Does BizSight Do?

BizSight simplifies the process of converting raw business data into meaningful insights.

A typical workflow looks like this:

**Upload Data → Clean Data → Map Columns → Analyze → Generate Insights → Visualize Results**

Users can upload their business data in formats such as:

* `.CSV`
* `.XLS`
* `.XLSX`

BizSight then processes the uploaded data and calculates important business metrics such as:

* Revenue
* Cost of Goods Sold (COGS)
* Gross Profit
* Net Profit
* Number of Orders
* Average Order Value (AOV)
* Customer Acquisition Cost (CAC)
* Repeat Purchase Rate
* Return/Cancel Rate
* Shipping Revenue
* Marketing Spend

The application also generates easy-to-understand business insights and recommendations.

---

# ✨ Key Features

### 📁 Data Upload

Users can upload their business orders, sales, and financial data through the application.

Supported formats:

* CSV
* Excel XLS
* Excel XLSX

---

### 🧹 Automatic Data Cleaning

BizSight processes the uploaded dataset and performs data-cleaning operations such as:

* Detecting duplicate records
* Handling missing values
* Removing irrelevant data
* Standardizing data
* Preparing the dataset for analysis

This reduces the amount of manual data preparation required from the user.

---

### 🔄 Column Mapping

Different businesses may use different column names for the same information.

For example:

```text
Customer Name
Client Name
Buyer Name
Customer
```

BizSight helps identify and map these columns to the required business fields.

Users can review the suggested mapping before continuing with the analysis.

---

### 📈 Business Analytics

BizSight calculates important financial and statistical metrics from the uploaded data.

Some of the major metrics include:

| Metric               | Description                                     |
| --------------------- | ------------------------------------------------ |
| Revenue               | Total sales generated                            |
| COGS                  | Cost associated with products sold               |
| Gross Profit          | Revenue minus COGS                               |
| Net Profit            | Profit after applicable expenses                 |
| Orders                | Total number of orders                           |
| AOV                   | Average value of each order                      |
| CAC                   | Estimated customer acquisition cost              |
| Repeat Purchase Rate  | Percentage of customers making repeat purchases  |
| Return/Cancel Rate    | Percentage of returned or cancelled orders       |
| Marketing Spend       | Total marketing expenditure                      |

---

### 🤖 AI / LLM-Based Insights

BizSight can use an **LLM (Large Language Model)** to transform analytical results into understandable business insights.

Instead of showing only numbers, the application aims to answer questions such as:

* What is happening with the business?
* Is the business profitable?
* Which areas need attention?
* What trends can be observed?
* What actions could improve business performance?

---

### 📊 Interactive Dashboard

The analyzed results are presented through an interactive dashboard.

The dashboard provides visual representations of important business metrics using charts, graphs, and summary cards.

This allows business owners to understand their business performance quickly.

---

# 🛠️ Technologies Used

BizSight is built using the following technologies:

* **Python**
* **Pandas**
* **FastAPI**
* **Next.js**
* **React**
* **Tailwind CSS**
* **LLM**
* **JavaScript**
* **HTML/CSS**

---

# 🏗️ Application Architecture

The overall architecture of BizSight can be understood as:

```text
                    ┌──────────────────┐
                    │      User        │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   Next.js /      │
                    │   React Frontend │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   File Upload    │
                    │   & Mapping      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Next.js API      │
                    │ Routes           │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ FastAPI Backend  │
                    └────────┬─────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │       Python Pipeline       │
              │                             │
              │  Data Cleaning              │
              │       ↓                     │
              │  Column Mapping             │
              │       ↓                     │
              │  Metric Calculation         │
              │       ↓                     │
              │  Business Insights          │
              └──────────────┬──────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Results / Data   │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ React Dashboard  │
                    │ & Visualizations │
                    └──────────────────┘
```

---

# 📂 Project Structure

The repository is organized into two major parts:

```text
BizSight/
│
├── frontend/
│   │
│   ├── app/
│   │   ├── api/
│   │   │   ├── process/
│   │   │   │   └── route.js
│   │   │   │
│   │   │   └── suggest-mapping/
│   │   │       └── route.js
│   │   │
│   │   ├── components/
│   │   │   ├── Navbar.jsx
│   │   │   ├── Hero.jsx
│   │   │   ├── HowItWorks.jsx
│   │   │   ├── Features.jsx
│   │   │   ├── FileUpload.jsx
│   │   │   ├── MappingReview.jsx
│   │   │   └── Dashboard.jsx
│   │   │
│   │   ├── analyze/
│   │   │   └── page.js
│   │   │
│   │   └── page.js
│   │
│   ├── package.json
│   └── ...
│
├── python-service/
│   │
│   ├── pipeline/
│   │   ├── cleaning.py
│   │   ├── mapping.py
│   │   └── metrics.py
│   │
│   ├── main.py
│   └── requirements.txt
│
├── sample_messy_orders.csv
├── .gitignore
└── README.md
```

---

# 🔍 Main Components

## Frontend

The frontend is responsible for the user interface and user interaction.

### `Navbar.jsx`

Contains the main navigation bar of the application.

### `Hero.jsx`

Contains the main landing-page introduction and call-to-action.

### `HowItWorks.jsx`

Explains the BizSight workflow to users.

### `Features.jsx`

Displays the major features of the application.

### `FileUpload.jsx`

Handles uploading business datasets.

### `MappingReview.jsx`

Allows users to review and confirm the automatically suggested column mapping.

### `Dashboard.jsx`

Displays the calculated business metrics and visualizations.

### `analyze/page.js`

Controls the main analysis workflow:

```text
Upload
   ↓
Mapping
   ↓
Processing
   ↓
Results
```

---

# 🐍 Python Service

The Python service handles the core data-processing and analytics operations.

## `main.py`

This is the **FastAPI entry point**.

It receives requests from the frontend and connects the API with the Python processing pipeline.

---

## `cleaning.py`

Responsible for preparing the uploaded dataset.

Typical operations include:

* Handling missing values
* Removing duplicates
* Cleaning inconsistent values
* Preparing data for analysis

---

## `mapping.py`

Responsible for identifying and suggesting mappings between the user's dataset columns and BizSight's required fields.

---

## `metrics.py`

Responsible for calculating the main business metrics.

It also generates rule-based business insights based on the calculated results.

---

# 🔄 Complete Data Flow

When a user uses BizSight, the following process takes place:

### Step 1 — Upload

The user uploads a CSV or Excel file.

```text
User
 ↓
FileUpload.jsx
```

### Step 2 — Column Detection

BizSight examines the uploaded dataset and suggests appropriate column mappings.

```text
Uploaded Dataset
 ↓
Mapping API
 ↓
Suggested Mapping
```

### Step 3 — Mapping Review

The user reviews the suggested mapping and can make changes if required.

```text
Suggested Mapping
 ↓
User Review
 ↓
Confirmed Mapping
```

### Step 4 — Data Processing

The confirmed dataset is sent for processing.

```text
Next.js API
 ↓
FastAPI
 ↓
Python Pipeline
```

### Step 5 — Data Cleaning

The Python service cleans and prepares the dataset.

```text
Raw Data
 ↓
Cleaning
 ↓
Clean Data
```

### Step 6 — Metric Calculation

BizSight calculates financial and statistical metrics.

```text
Clean Data
 ↓
Metrics Engine
 ↓
Business Metrics
```

### Step 7 — Insights

The system generates understandable business insights and recommendations.

```text
Business Metrics
 ↓
Insights / LLM
 ↓
Business Recommendations
```

### Step 8 — Dashboard

The final results are returned to the frontend and displayed through the interactive dashboard.

```text
Results
 ↓
React Dashboard
 ↓
Charts + Metrics + Insights
```

---

# 💻 Running BizSight Locally

## Prerequisites

Before running the project, make sure you have installed:

* Python
* Node.js
* npm

---

## 1. Clone the Repository

```bash
git clone https://github.com/amuqeet6041/bizzsight.git
```

Move into the project directory:

```bash
cd bizzsight
```

---

# 2. Set Up the Python Service

Navigate to the Python service:

```bash
cd python-service
```

Create a virtual environment:

### Windows

```bash
python -m venv venv
```

Activate it:

```bash
venv\Scripts\activate
```

Install the required Python packages:

```bash
pip install -r requirements.txt
```

Start the FastAPI server:

```bash
uvicorn main:app --reload
```

The Python backend should now be running locally.

---

# 3. Set Up the Frontend

Open another terminal.

Navigate to the frontend:

```bash
cd frontend
```

Install the required Node.js packages:

```bash
npm install
```

Start the Next.js development server:

```bash
npm run dev
```

The frontend will be available at:

```text
http://localhost:3000
```

---

# 🧪 Testing the Application

A sample dataset is included in the repository:

```text
sample_messy_orders.csv
```

You can use this file to test the complete BizSight workflow.

Recommended testing flow:

```text
Upload sample_messy_orders.csv
        ↓
Review Column Mapping
        ↓
Confirm Mapping
        ↓
Process Dataset
        ↓
View Metrics
        ↓
View Dashboard
        ↓
Review Business Insights
```

---

# 🌐 Deployment

The BizSight frontend is deployed using **Vercel**.

Production application:

**https://www.bizzsight.vercel.app**

The GitHub repository contains the source code for the project.

---

# 👨‍💻 Project Team

### Abdul Muqeet

**Project Lead & Lead Developer**

Responsible for designing and developing the complete BizSight application, including frontend, backend, data processing, analytics, integration, and deployment.

### Manahil

**Presentation & QA**

Responsible for preparing the PowerPoint presentation and assisting with application testing and quality assurance.

### Areeba

**Demo, Presentation & QA**

Responsible for application testing, live demonstration, video recording, and presentation.

### Faiza

**Research & Documentation**

Contributed to project research, content organization, and documentation support.

---

# 🎯 Project Objective

The main objective of BizSight is to make **business analytics more accessible to SMEs and online businesses**.

Many small businesses collect large amounts of sales and customer data but do not have dedicated data analysts or the technical knowledge required to interpret that data.

BizSight aims to bridge this gap by providing a simple workflow:

> **Upload your data → Let BizSight analyze it → Understand your business → Make better decisions.**

---

# 🔮 Future Improvements

Potential future versions of BizSight could include:

* Shopify integration
* WooCommerce integration
* Direct website data extraction
* More advanced AI-powered recommendations
* Predictive analytics
* Sales forecasting
* Customer segmentation
* Product-level profitability analysis
* Automated Power BI dashboard generation
* More advanced financial analysis
* Real-time business analytics
* Multi-business/user accounts

---

# 📌 Project Status

**Current Status: Functional Prototype / Hackathon Project**

BizSight currently supports the core workflow of:

**Data Upload → Cleaning → Column Mapping → Business Analysis → Insights → Dashboard**

The architecture is designed so additional data sources, analytics features, and AI capabilities can be integrated in future versions.

---

## ⭐ If You Find This Project Interesting

Feel free to explore the repository, test the application using the provided sample dataset, and contribute improvements.

**Built with Python, FastAPI, Next.js, React, Tailwind CSS, Pandas & LLM technologies.**

---

### Developed by Abdul Muqeet
