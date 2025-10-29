# CuStateGen - Customer Statement Generator & Business Intelligence

## 📋 Overview

**CuStateGen** is a comprehensive Odoo module that bridges your existing ERPNext system with professional customer statement generation and advanced material/supplier analytics.

### What It Does
- **Customer Management**: Sync and manage customer accounts from ERPNext
- **Professional Statements**: Generate branded customer account statements with aging analysis
- **Material Analytics**: Analyze purchase patterns, repeated materials, and supplier performance
- **Supplier Intelligence**: Track supplier reliability, pricing trends, and material sourcing
- **Payment Predictions**: AI-powered payment date predictions using the Forecaster module

### Perfect For
✅ Businesses using ERPNext for operations but needing better customer-facing reports  
✅ Companies wanting to analyze supplier/material purchase patterns  
✅ Organizations needing professional, branded customer statements  
✅ Teams requiring business intelligence on purchasing decisions  

---

## 🏗️ Module Structure

```
custom-addons/CuStateGen/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── customer_account.py          # Customer sync from ERPNext
│   ├── customer_statement.py        # Statement generation logic
│   ├── statement_line.py            # Transaction lines
│   ├── material_analysis.py         # Material purchase analytics
│   ├── supplier_analytics.py        # Supplier performance tracking
│   └── statement_template.py        # Customizable templates
├── wizards/
│   ├── __init__.py
│   ├── statement_generator_wizard.py  # Single/bulk generation
│   └── bulk_sync_wizard.py            # Bulk operations
├── views/
│   ├── customer_account_views.xml
│   ├── customer_statement_views.xml
│   ├── material_analysis_views.xml
│   ├── supplier_analytics_views.xml
│   └── dashboard_views.xml
├── wizards/
│   ├── statement_generator_wizard_views.xml
│   └── bulk_sync_wizard_views.xml
├── reports/
│   ├── statement_report.xml          # PDF statement template
│   └── material_report.xml           # Material analysis report
├── data/
│   └── default_templates.xml
├── security/
│   └── ir.model.access.csv
└── README.md
```

---

## 📦 Installation

### Prerequisites
1. **Existing Modules Required**:
   - `erpnext_connector` (your ERPNext integration)
   - `Forecaster` (for payment predictions - optional)
   - `base`, `account` (Odoo standard)

2. **ERPNext Access**:
   - API Key & Secret configured
   - Permissions for: Customer, Sales Invoice, Payment Entry, Purchase Invoice

### Install Steps

1. **Copy module to addons**:
```bash
cp -r CuStateGen /path/to/odoo/custom-addons/
```

2. **Update Odoo apps list**:
```bash
./odoo-bin -c odoo.conf -u all -d your_database
```

3. **Install via UI**:
   - Go to Apps → Update Apps List
   - Search "CuStateGen"
   - Click Install

---

## ⚙️ Configuration

### 1. ERPNext Connection (Already Done)
Your existing `erpnext_connector` module handles this. Just ensure it's active.

### 2. Sync Customers

**Option A: Bulk Sync (Recommended for first time)**
```
Navigate to: CuStateGen → Bulk Operations → Bulk Sync
- Select "Sync Customers"
- Optionally filter by Customer Group
- Click "Start Sync"
```

**Option B: Individual Sync**
```
Navigate to: CuStateGen → Customers → Create
- Enter ERPNext Customer ID
- Click "Sync from ERPNext"
```

### 3. Configure Statement Templates

```
Navigate to: CuStateGen → Configuration → Statement Templates

Default Template includes:
- Company logo and branding
- Bank details
- Aging analysis (30/60/90 days)
- Payment terms
- Custom footer messages
```

**Customize Template**:
- Upload your logo
- Set brand colors (header/accent)
- Add bank account details
- Customize footer message
- Enable/disable sections (aging, payment terms, etc.)

---

## 🚀 Usage Guide

### Generating Customer Statements

#### **Single Statement**

1. Navigate to **CuStateGen → Customers**
2. Open a customer record
3. Click **"Generate Statement"** button
4. In the wizard:
   - Select date range (or use presets: Current Month, Last Quarter, etc.)
   - Choose template
   - Enable options:
     - ✅ Include Opening Balance
     - ✅ Include Aging Analysis
     - ✅ Auto-send via Email
   - Click **"Generate Statements"**

#### **Bulk Generation**

1. Navigate to **CuStateGen → Bulk Operations → Bulk Sync**
2. Select **"Generate Statements"**
3. Set date range
4. Choose:
   - **All customers** (generates for everyone)
   - **Selected customers** (multi-select)
5. Click **"Start Sync"**

### Statement Features

**What's Included in Each Statement**:
- ✅ Customer details and contact info
- ✅ Opening balance
- ✅ All invoices in period (with due dates)
- ✅ All payments received
- ✅ Credit notes applied
- ✅ Running balance per transaction
- ✅ Aging analysis (Current, 30, 60, 90, 90+ days)
- ✅ Closing balance
- ✅ **AI Predicted Payment Date** (if Forecaster is installed)

**Statement Actions**:
- 📄 **Print PDF**: Professional branded PDF
- 📧 **Email**: Send directly to customer
- 💾 **Download**: Save locally
- 🔄 **Refresh**: Re-fetch from ERPNext

---

## 📊 Material & Supplier Analytics

### Material Purchase Analysis

**Purpose**: Identify purchasing patterns, repeated materials, and cost trends

**How to Generate**:

1. Navigate to **CuStateGen → Analytics → Material Analysis**
2. Click **Create** or use **Bulk Operations → Analyze Materials**
3. Set analysis period (e.g., last 6 months)
4. Click **"Analyze Materials"**

**What You Get**:
- 📦 Total materials purchased
- 💰 Total purchase value
- 🔁 Repeated purchases (materials bought 2+ times)
- 📈 Price trends (increasing/stable/decreasing)
- 👥 Unique suppliers count
- 🏆 Top materials by value
- 🏢 Top suppliers by value

**Material Line Details**:
- Material code and name
- Purchase count
- Total quantity and value
- Average unit price
- Primary supplier
- Number of alternate suppliers
- Purchase frequency (one-time, occasional, regular, frequent)
- Price trend indicator
- Last purchase date

**Use Cases**:
✅ **Identify repeated purchases** → Negotiate bulk discounts  
✅ **Detect price increases** → Find alternative suppliers  
✅ **Track supplier diversity** → Reduce single-supplier risk  
✅ **Spot unnecessary spending** → Consolidate similar materials  

---

### Supplier Performance Analytics

**Purpose**: Evaluate supplier reliability and pricing competitiveness

**How to Use**:

1. Navigate to **CuStateGen → Analytics → Supplier Analytics**
2. System auto-generates based on purchase data
3. View metrics:
   - Total purchase value per supplier
   - Number of invoices
   - Unique materials supplied
   - Average invoice value
   - Days since last purchase
   - On-time delivery rate (if tracked in ERPNext)

**Supplier Comparison**:
- Select multiple suppliers
- Click **"Compare Suppliers"**
- View side-by-side graphs and pivots

**Use Cases**:
✅ **Identify preferred suppliers** → Strengthen relationships  
✅ **Find inactive suppliers** → Clean up vendor list  
✅ **Compare pricing** → Negotiate better rates  
✅ **Track delivery performance** → Set quality standards  

---

## 🎯 Business Intelligence Reports

### Key Metrics Dashboard

Navigate to **CuStateGen → Dashboard** to view:

#### **Customer Health Metrics**
- 💵 Total Outstanding Balance
- ⏰ Average Days Since Payment
- 🚨 Customers Over Credit Limit
- 📉 Payment Trend (improving/declining)

#### **Material Insights**
- 📦 Total Materials Purchased
- 🔁 Repeated Purchase Rate
- 💰 Average Material Cost
- 📈 Price Volatility Score

#### **Supplier Intelligence**
- 👥 Active Suppliers
- 🏆 Top 5 Suppliers by Value
- 📊 Supplier Concentration Risk
- ⭐ Average Supplier Rating

---

## 🔍 Advanced Features

### 1. **AI Payment Prediction** (Requires Forecaster)

When generating statements, the system:
- Analyzes customer payment history
- Calculates average payment delay
- Predicts next payment date with confidence score
- Displays in statement: "Expected payment: 2025-12-15 (85% confidence)"

**How it works**:
```python
# Automatic calculation based on:
- Past payment patterns
- Invoice aging
- Seasonal trends
- Customer payment velocity
```

### 2. **Aging Analysis**

Every statement includes automatic aging buckets:
- **Current**: Not yet due
- **30 Days**: 1-30 days overdue
- **60 Days**: 31-60 days overdue
- **90 Days**: 61-90 days overdue
- **90+ Days**: Over 90 days overdue

### 3. **Price Trend Detection**

Material analysis automatically detects:
- **Increasing**: Prices rising >10% vs average
- **Stable**: Within ±10% of average
- **Decreasing**: Prices falling >10% vs average

### 4. **Repeated Purchase Detection**

Flags materials bought 2+ times for:
- Bulk negotiation opportunities
- Inventory optimization
- Supplier consolidation

---

## 📋 Workflows

### **Monthly Statement Generation Workflow**

```
1. First day of month
   └─> Run: CuStateGen → Bulk Operations → Generate Statements
       ├─> Period: "Last Month"
       ├─> For: "All Customers"
       └─> Enable: "Auto-send via Email"

2. Review generated statements
   └─> Navigate to: CuStateGen → Statements
       └─> Filter: "Last Month"

3. Follow up on overdue accounts
   └─> Use filter: "90+ Days Overdue"
       └─> Mark priority customers
```

### **Quarterly Supplier Review Workflow**

```
1. End of quarter
   └─> Run: CuStateGen → Analytics → Material Analysis
       └─> Period: "Last Quarter"

2. Review insights
   ├─> Check "Repeated Materials" tab
   ├─> Identify price increases
   └─> Note inactive suppliers

3. Take action
   ├─> Negotiate with top 5 suppliers
   ├─> Request quotes from alternates
   └─> Consolidate fragmented purchases
```

---

## 🔧 Customization

### Custom Statement Templates

**Create New Template**:
```
Navigate to: CuStateGen → Configuration → Templates → Create

Required:
- Template Name
- Company Logo
- Header Color
- Footer Message

Optional:
- Bank Details
- Terms & Conditions
- Custom Sections
```

**Available Placeholders** (for custom text):
```
${customer_name}
${statement_number}
${date_from}
${date_to}
${opening_balance}
${closing_balance}
${total_invoiced}
${total_paid}
```

### Custom Material Grouping

Extend `material.analysis.line` to add:
- Custom categories
- Department classifications
- Project allocations

---

## 📊 Reports & Exports

### Available Reports

1. **Customer Statement (PDF)**
   - Professional branded layout
   - Transaction details
   - Aging analysis
   - Payment terms

2. **Material Analysis Report (Excel)**
   - Material code, name, group
   - Purchase frequency
   - Price trends
   - Supplier details

3. **Supplier Comparison (Pivot)**
   - Side-by-side metrics
   - Performance graphs
   - Cost analysis

### Export Options

**Customer Data**:
```
Navigate to: Customers → Tree View → Action → Export
Fields: Name, Outstanding, Days Overdue, Last Payment
```

**Material Analysis**:
```
Navigate to: Material Analysis → Export
Gets: All materials with purchase history and trends
```

---

## 🔐 Security & Permissions

### User Groups

**Statement Users** (`base.group_user`):
- ✅ View customers and statements
- ✅ Generate single statements
- ✅ View analytics (read-only)
- ❌ Cannot delete or bulk operations

**Account Managers** (`account.group_account_manager`):
- ✅ Full access to all features
- ✅ Create/edit/delete records
- ✅ Bulk operations
- ✅ Configure templates

### Data Privacy

- Customer data synced from ERPNext only
- Statements stored in Odoo database
- Email sending uses Odoo mail server
- No external API calls except to configured ERPNext

---

## 🐛 Troubleshooting

### Issue: "No customers found"
**Solution**: Run bulk customer sync first
```
CuStateGen → Bulk Operations → Bulk Sync → Sync Customers
```

### Issue: "Failed to fetch from ERPNext"
**Check**:
1. ERPNext Connector is active: `ERPNext → Configuration`
2. API credentials are valid: Click "Test Connection"
3. User has permissions in ERPNext for: Customer, Sales Invoice, Payment Entry

### Issue: "Statement shows no transactions"
**Possible Causes**:
- No transactions in selected date range
- Customer ID mismatch between Odoo and ERPNext
- ERPNext documents not "Submitted" (must be docstatus=1)

**Fix**:
1. Check date range
2. Verify customer ERPNext ID matches: `Customer → Sync Information tab`
3. Check ERPNext for submitted documents

### Issue: "Material analysis shows no data"
**Solution**: 
- Ensure Purchase Invoices exist in ERPNext for the period
- Check that invoices are submitted (not draft)
- Verify ERPNext API permissions include Purchase Invoice

---

## 🚀 Performance Tips

### For Large Datasets

1. **Incremental Syncs**: Use date filters instead of "sync all"
2. **Scheduled Jobs**: Set up cron for automated statement generation
3. **Archive Old Statements**: Move 1-year+ old statements to archive

### Cron Job Examples

**Auto-generate monthly statements** (add to Odoo cron):
```xml
<record id="cron_monthly_statements" model="ir.cron">
    <field name="name">Generate Monthly Statements</field>
    <field name="model_id" ref="model_customer_statement"/>
    <field name="state">code</field>
    <field name="code">
# Run on 1st of each month
wizard = env['statement.generator.wizard'].create({
    'period_type': 'last_month',
    'generate_for_all': True,
    'auto_send_email': True
})
wizard.action_generate_statements()
    </field>
    <field name="interval_number">1</field>
    <field name="interval_type">months</field>
</record>
```

---

## 📚 API Reference

### Python API

#### Generate Statement Programmatically

```python
# Get customer
customer = env['customer.account'].search([('name', '=', 'CUST-001')])

# Create statement
statement = env['customer.statement'].create({
    'customer_id': customer.id,
    'date_from': '2025-11-01',
    'date_to': '2025-11-30',
})

# Fetch from ERPNext
statement.action_fetch_from_erpnext()

# Generate PDF
pdf = env.ref('CuStateGen.action_report_customer_statement').render_qweb_pdf(statement.id)
```

#### Bulk Material Analysis

```python
# Create analysis
analysis = env['material.analysis'].create({
    'name': 'Q4 2025 Analysis',
    'date_from': '2025-10-01',
    'date_to': '2025-12-31',
})

# Run analysis
analysis.action_analyze_materials()

# Get top 10 materials
top_materials = analysis.material_line_ids.sorted('total_value', reverse=True)[:10]
```

---

## 🎓 Training & Support

### Quick Start Guide

**Day 1**: Setup
- Install module
- Sync customers from ERPNext
- Create default template

**Day 2**: First Statements
- Generate statements for top 10 customers
- Review and customize template
- Test email sending

**Day 3**: Analytics
- Run material analysis for last quarter
- Review supplier analytics
- Identify cost-saving opportunities

### Video Tutorials (Placeholder)
- [ ] Customer Sync Process
- [ ] Statement Generation Walkthrough
- [ ] Material Analytics Deep Dive
- [ ] Custom Template Design

---

## 🆘 Support

### Community
- GitHub Issues: [Your Repo URL]
- Odoo Forum: Tag `custategen`

### Commercial Support
Contact: support@yourcompany.com

---

## 📄 License

LGPL-3

---

## 🎉 Credits

**Developed for**: Businesses bridging ERPNext with professional customer-facing reports

**Integrates with**:
- ERPNext Connector (your existing module)
- Forecaster (payment predictions)
- GMailer (optional bank statement linking)

---

## 🔄 Changelog

### Version 1.0.0 (Current)
- ✨ Initial release
- ✅ Customer account sync
- ✅ Professional statement generation
- ✅ Material purchase analytics
- ✅ Supplier performance tracking
- ✅ AI payment predictions
- ✅ Customizable templates
- ✅ Bulk operations

### Roadmap
- [ ] Multi-currency support
- [ ] Custom report builder
- [ ] WhatsApp statement delivery
- [ ] Automated dunning letters
- [ ] Customer portal access

---

**Happy Reporting! 📊**