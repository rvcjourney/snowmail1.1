# Preview Data Feature - Complete Guide ✅

## 🎯 Overview

The **Preview Data** tab allows you to view all extracted email data in a professional, organized table format. This feature is now fully integrated with the new professional UI redesign.

---

## 📋 What is Preview Data?

Preview Data displays all the emails and information that have been extracted from the selected domains. It shows:

- **First Name** - Extracted contact's first name
- **Job Title** - Job designation/title
- **Company** - Company name
- **Location** - Geographic location
- **Email** - Contact's email address (highlighted in blue)
- **Domain** - Source domain where data was extracted

---

## 🚀 How to Use

### Step 1: Run an Extraction
1. Go to **Configuration** tab
2. Fill in your extraction parameters
3. Click **"Start Extraction"**
4. Wait for extraction to complete

### Step 2: View Preview Data
1. Click **"Preview Data"** tab in the sidebar
2. You'll see a table with all extracted contacts
3. Each row represents one extracted contact

### Step 3: Review the Data
- **Total Records** shows count at the top
- **Email addresses** are highlighted in blue
- Scroll down to see more records
- All fields display clearly with proper formatting

---

## 📊 Table Columns

| Column | Description | Example |
|--------|-------------|---------|
| **First Name** | Contact's first name | John |
| **Job Title** | Job designation | Manager, Developer, Sales |
| **Company** | Company/organization | Google, Amazon, Microsoft |
| **Location** | City/Region | New York, San Francisco |
| **Email** | Email address (highlighted) | john.doe@company.com |
| **Domain** | Source domain | google.com, amazon.com |

---

## 🎨 Visual Features

### Professional Table Design
- ✅ **Gradient header** with professional colors
- ✅ **Clean rows** with proper spacing
- ✅ **Hover effects** on table rows (light blue highlight)
- ✅ **Email highlighting** in blue (#3498db)
- ✅ **Responsive layout** for all screen sizes

### Empty State
When no data has been extracted yet:
- Shows mailbox icon (📭)
- Displays helpful message
- Encourages user to start extraction

### Data Counter
Shows total number of extracted records at the top:
```
Total Records: 42
```

---

## 🔄 Data Flow

```
┌─────────────────────────┐
│  Configuration Tab      │
│  - Enter domains        │
│  - Click "Extract"      │
└────────┬────────────────┘
         │
         ↓
┌─────────────────────────┐
│  Backend Processing     │
│  - Scrapes websites     │
│  - Finds emails         │
│  - Sends data to UI     │
└────────┬────────────────┘
         │
         ↓
┌─────────────────────────┐
│  Preview Data Tab       │
│  - Display in table     │
│  - Show all records     │
│  - Update in real-time  │
└─────────────────────────┘
```

---

## 📱 Features Explained

### 1. **Live Updates**
As extraction continues:
- New records appear in the table immediately
- Count updates in real-time
- No page refresh needed

### 2. **Professional Styling**
- Modern color scheme (#3498db, #2d3e50)
- Clean typography with proper hierarchy
- Glass-morphism effects on card
- Shadow effects for depth

### 3. **Email Highlighting**
- All email addresses display in **professional blue** (#3498db)
- **Bold font** weight for emphasis
- Easy to spot contact information

### 4. **Responsive Table**
- Works on desktop and larger screens
- Proper scrolling on small screens
- All columns visible with proper width
- Text alignment optimized

### 5. **Empty State Handling**
When no data extracted:
- Shows friendly empty state
- Icon and message for clarity
- Encourages next action

---

## 💡 Usage Tips

### Tip 1: Switch Between Tabs
Click "Configuration" and "Preview Data" to switch views:
- **Configuration** - Set extraction parameters
- **Preview Data** - View extracted data

### Tip 2: Review During Extraction
You can switch to Preview Data **while extraction is running**:
- See emails as they're extracted
- Count increases in real-time
- Perfect for monitoring progress

### Tip 3: Multiple Extractions
Each extraction **appends to the table**:
- Old data stays
- New data gets added
- Total count increases

### Tip 4: Export Consideration
The extracted data shown here is the same data you can:
- Download as CSV (if export feature used)
- Copy manually from the table
- Reference for outreach

---

## 🧪 Test the Preview Data

### Quick Test:
1. **Configuration Tab:**
   - Domain: `tatamotors.com`
   - Designation: `manager`
   - Emails: `50`
   - Click "Start Extraction"

2. **Watch Progress:**
   - See Activity Log updates
   - Watch statistics update
   - See live email count

3. **Switch to Preview Data:**
   - Click "Preview Data" tab
   - See extracted contacts in table
   - Review email addresses

4. **Observe Features:**
   - ✅ Email addresses in blue
   - ✅ All data properly formatted
   - ✅ Professional table styling
   - ✅ Smooth layout

---

## 📊 Example Data Display

```
┌──────────┬─────────────┬──────────┬───────────┬─────────────────────────┬─────────────┐
│First Name│ Job Title   │ Company  │ Location  │ Email                   │ Domain      │
├──────────┼─────────────┼──────────┼───────────┼─────────────────────────┼─────────────┤
│John      │ Manager     │ Tata     │ Mumbai    │ john.smith@tatamotors.* │ tatamotors. │
│Sarah     │ Manager     │ Tata     │ Delhi     │ sarah.johnson@tatamotors│ tatamotors. │
│Rajesh    │ Developer   │ Tata     │ Bangalore │ rajesh.patel@tatamotors │ tatamotors. │
│Priya     │ Sales Lead  │ Tata     │ Hyderabad │ priya.sharma@tatamotors │ tatamotors. │
└──────────┴─────────────┴──────────┴───────────┴─────────────────────────┴─────────────┘
```

---

## 🎨 Design Details

### Table Header
- Background: Linear gradient (#2d3e50 to #34495e)
- Text: White, bold, uppercase
- Padding: 18px 16px
- Shadow: 0 2px 8px rgba(0, 0, 0, 0.1)

### Table Rows
- Background: White
- Border: 1px solid #ecf0f1
- Padding: 16px
- Hover: Light blue background (#f5f7fa)

### Email Column
- Color: #3498db (professional blue)
- Font-weight: 600 (bold)
- Easy to identify at a glance

### Empty State
- Icon: 📭 (mailbox)
- Color: #999999 (gray)
- Text: Helpful message

---

## 🔄 Real-Time Behavior

### During Extraction:
1. Switch to Preview Data tab
2. Table updates live with new records
3. Email count increases in header
4. No delay in data display
5. Can see progress in real-time

### After Extraction:
1. All records visible in table
2. Can review complete dataset
3. Switch back to Configuration for next extraction
4. New extraction adds to existing data

---

## 💾 Data Persistence

### Session Data:
- Data stays in table during session
- Survives tab switching
- Survives Configuration changes

### Persistence:
- Clear by clicking "Reset Form" button
- Or by refreshing page
- Or by starting new extraction (appends)

---

## ⚙️ Technical Details

### Component Structure:
```javascript
// Preview Data Tab Content
{activeTab === 'preview' && (
  <div style={styles.contentCard}>
    {/* Header with record count */}
    {/* Empty state OR Table */}
    {previewData.length === 0 ? (
      <EmptyState />
    ) : (
      <Table data={previewData} />
    )}
  </div>
)}
```

### Data Source:
```javascript
const [previewData, setPreviewData] = useState([]);

// Updated via socket event
socket.on('preview_data', (data) => {
  data.previewData.forEach((item) => {
    previewSet.current.add(JSON.stringify(item));
  });
  setPreviewData(Array.from(previewSet.current).map(JSON.parse));
});
```

### Table Rendering:
```javascript
<table style={styles.table}>
  <thead>
    <tr>
      <th>First Name</th>
      <th>Job Title</th>
      {/* ... more columns ... */}
    </tr>
  </thead>
  <tbody>
    {previewData.map((item, index) => (
      <tr key={index}>
        <td>{item['First Name']}</td>
        {/* ... more cells ... */}
      </tr>
    ))}
  </tbody>
</table>
```

---

## 🎯 When to Use Preview Data

### ✅ Use When:
- You want to review extracted contacts
- You need to verify data quality
- You're checking for specific emails
- You want to see complete dataset
- You're preparing for outreach
- You need to copy data manually

### ❌ Not Needed When:
- You just want email count
- You're running extraction
- You're setting parameters
- You plan to download CSV

---

## 🔐 Data Privacy

### Data Shown:
- Only extracted information
- Same data as backend response
- Professional names and emails
- Company and location info

### Data Not Shown:
- Raw HTML or DOM data
- Intermediate processing data
- Credentials or sensitive info
- System logs

---

## 🚀 Performance Notes

- **Load Time:** Instant (client-side rendering)
- **Scroll Performance:** Smooth (optimized table)
- **Memory:** Minimal (data stored in state)
- **Update Speed:** Real-time (no refresh needed)

---

## 📞 Troubleshooting

### Issue: Preview Data Tab Empty
**Solution:**
1. Start an extraction first
2. Data appears as it's extracted
3. Check Configuration tab for activity

### Issue: Data Not Updating
**Solution:**
1. Ensure backend is running
2. Check browser console for errors
3. Verify extraction is in progress
4. Refresh page if needed

### Issue: Email Addresses Not Highlighted
**Solution:**
1. Normal for non-email columns
2. Email column always blue
3. Check browser theme settings
4. Try different browser

### Issue: Table Not Visible
**Solution:**
1. Click "Preview Data" tab
2. Start an extraction first
3. Wait for completion
4. Check browser zoom level

---

## ✨ Features Summary

✅ **Professional Table Design** - Modern, clean styling
✅ **Real-Time Updates** - Data appears as it's extracted
✅ **Email Highlighting** - Blue color for easy identification
✅ **Record Counter** - Shows total extracted count
✅ **Empty State** - Friendly message when no data
✅ **Responsive Layout** - Works on all screen sizes
✅ **Smooth Interactions** - Hover effects and transitions
✅ **Data Accuracy** - Same as backend response

---

## 🎉 You're All Set!

The **Preview Data** feature is now fully integrated with your professional UI redesign. You can:
- ✅ Extract emails efficiently
- ✅ Preview results immediately
- ✅ Review data quality
- ✅ Prepare for outreach
- ✅ Export if needed

**Enjoy using your enhanced Email Extractor!** 🚀

---

**Status: ✅ PREVIEW DATA FEATURE COMPLETE**
**Date: 2026-02-23**
**Integration: Fully working with professional UI**

