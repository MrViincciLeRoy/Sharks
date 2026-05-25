# CuStateGen
CuStateGen is a module designed to generate customer statements and material analytics from ERPNext, providing valuable insights into customer accounts and material purchases.
## Key Features
* Customer account statements with outstanding balances
* Invoice and payment history reports
* Credit note tracking and reconciliation
* Aging analysis (30/60/90 days)
* Material purchase analysis
* Supplier analytics
* Integration with Forecaster for payment predictions
* Optional bank transaction correlation
## Tech Stack
* Odoo
* ERPNext
* Python
## Installation
1. Install the CuStateGen module in your Odoo instance
2. Configure the module settings, including ERPNext integration and Forecaster settings
## Usage
1. Generate customer statements using the statement generator wizard
2. View customer account statements and analytics
3. Analyze material purchases and supplier performance
## Required Environment Variables
* `ERPNEXT_URL`: the URL of your ERPNext instance
* `ERPNEXT_API_KEY`: the API key for your ERPNext instance
* `FORECASTER_URL`: the URL of your Forecaster instance
* `FORECASTER_API_KEY`: the API key for your Forecaster instance