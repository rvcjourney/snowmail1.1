import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import {
  MdSettings, MdPlayCircle, MdRefresh,
  MdStorage, MdAccessTime,
  MdLocationOn, MdWorkHistory, MdMailOutline, MdDomain,
  MdNumbers, MdSaveAlt, MdDataObject, MdGridOn
} from 'react-icons/md';
// Use REACT_APP_BACKEND_URL env variable if set (Docker), else fallback to local dev
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://127.0.0.1:5003';
console.log('🔌 Connecting to backend at:', BACKEND_URL);

const socket = io(BACKEND_URL, {
  transports: ['polling'],
  pingInterval: 25000,       // 25 seconds — reasonable keepalive interval
  pingTimeout: 60000,        // 60 seconds — drop truly dead connections
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionAttempts: 10,
});

// Connection status logging
socket.on('connect', () => {
  console.log('✅ CONNECTED to backend! Socket ID:', socket.id);
});

socket.on('disconnect', () => {
  console.log('❌ DISCONNECTED from backend');
});

socket.on('connect_error', (error) => {
  console.error('❌ Connection Error:', error);
});

socket.on('error', (error) => {
  console.error('❌ Socket Error:', error);
});

socket.on('reconnect', () => {
  console.log('🔄 RECONNECTED to backend');
});

const styles = {
  // Full page layout - Professional gradient background
  container: {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #f5f7fa 0%, #e9f0f5 100%)',
    display: 'flex',
    fontFamily: '"Segoe UI", "Roboto", sans-serif',
  },
  
  // Sidebar navigation - Modern professional design
  sidebar: {
    width: '300px',
    background: 'linear-gradient(180deg, #2d3e50 0%, #34495e 100%)',
    color: '#ffffff',
    padding: '35px 25px',
    boxShadow: '0 10px 40px rgba(0, 0, 0, 0.15)',
    overflowY: 'auto',
    borderRight: '1px solid rgba(255, 255, 255, 0.1)',
  },

  sidebarTitle: {
    fontSize: '28px',
    fontWeight: '700',
    marginBottom: '35px',
    color: '#ffffff',
    paddingBottom: '20px',
    borderBottom: '2px solid #3498db',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  
  navItem: (active) => ({
    padding: '16px 18px',
    margin: '12px 0',
    borderRadius: '10px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: active ? '600' : '500',
    background: active ? '#3498db' : 'rgba(255, 255, 255, 0.08)',
    color: '#ffffff',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    border: active ? '2px solid #3498db' : '2px solid transparent',
    width: '100%',
    textAlign: 'left',
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    boxShadow: active ? '0 4px 15px rgba(52, 152, 219, 0.3)' : 'none',
  }),

  statsSection: {
    marginTop: '45px',
    paddingTop: '25px',
    borderTop: '1px solid rgba(255, 255, 255, 0.1)',
  },

  statsLabel: {
    fontSize: '13px',
    fontWeight: '700',
    color: '#bdc3c7',
    textTransform: 'uppercase',
    marginBottom: '16px',
    letterSpacing: '1px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },

  statItem: {
    padding: '16px 14px',
    background: 'rgba(255, 255, 255, 0.08)',
    borderRadius: '10px',
    marginBottom: '12px',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    backdropFilter: 'blur(10px)',
  },

  statValue: {
    fontSize: '28px',
    fontWeight: '700',
    color: '#3498db',
    marginBottom: '6px',
  },

  statName: {
    fontSize: '13px',
    color: '#bdc3c7',
    fontWeight: '500',
  },
  
  // Main content area
  main: {
    flex: 1,
    padding: '40px',
    overflowY: 'auto',
    backgroundColor: 'transparent',
  },

  pageHeader: {
    marginBottom: '30px',
    paddingBottom: '20px',
    borderBottom: '2px solid rgba(52, 152, 219, 0.2)',
  },

  pageTitle: {
    fontSize: '34px',
    fontWeight: '700',
    color: '#2d3e50',
    marginBottom: '8px',
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },

  pageSubtitle: {
    fontSize: '16px',
    color: '#7f8c8d',
    fontWeight: '500',
  },

  // Content card - Professional glass-morphism effect
  contentCard: {
    background: 'rgba(255, 255, 255, 0.95)',
    borderRadius: '16px',
    boxShadow: '0 10px 40px rgba(0, 0, 0, 0.08)',
    padding: '40px',
    marginBottom: '30px',
    border: '1px solid rgba(255, 255, 255, 0.6)',
    backdropFilter: 'blur(10px)',
  },
  
  // Form grid layout
  formGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '24px',
    marginBottom: '24px',
  },
  
  formGridFull: {
    gridColumn: '1 / -1',
  },
  
  // Form field
  formField: {
    display: 'flex',
    flexDirection: 'column',
  },
  
  label: {
    fontSize: '13px',
    fontWeight: '600',
    color: '#1a1a2e',
    marginBottom: '8px',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  
  input: {
    padding: '13px 16px',
    borderRadius: '10px',
    border: '2px solid #dfe6e9',
    fontSize: '15px',
    fontFamily: 'inherit',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    backgroundColor: '#f8f9fa',
    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.04)',
  },

  textarea: {
    padding: '13px 16px',
    borderRadius: '10px',
    border: '2px solid #dfe6e9',
    fontSize: '15px',
    fontFamily: 'inherit',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    backgroundColor: '#f8f9fa',
    resize: 'vertical',
    minHeight: '100px',
    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.04)',
  },
  
  // Button group
  buttonGroup: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
    marginTop: '32px',
  },
  
  button: (bgColor, disabled) => ({
    padding: '14px 28px',
    backgroundColor: disabled ? '#e8e8e8' : bgColor,
    color: disabled ? '#999999' : '#ffffff',
    border: 'none',
    borderRadius: '10px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    fontSize: '15px',
    fontWeight: '600',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    boxShadow: disabled ? 'none' : `0 6px 20px rgba(${bgColor === '#00d4ff' ? '0, 212, 255' : '100, 100, 100'}, 0.25)`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
  }),
  
  // Status badge
  statusBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 16px',
    borderRadius: '20px',
    fontSize: '13px',
    fontWeight: '600',
  },
  
  // Progress section
  progressSection: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '16px',
    marginBottom: '30px',
  },
  
  progressCard: {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    padding: '28px',
    borderRadius: '14px',
    color: '#ffffff',
    textAlign: 'center',
    boxShadow: '0 8px 24px rgba(102, 126, 234, 0.35)',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
  },
  
  progressValue: {
    fontSize: '32px',
    fontWeight: '700',
    marginBottom: '8px',
  },
  
  progressLabel: {
    fontSize: '13px',
    fontWeight: '600',
    opacity: '0.9',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  
  // Activity log
  logSection: {
    background: 'linear-gradient(135deg, #f8f9fa 0%, #f0f2f5 100%)',
    borderRadius: '12px',
    padding: '28px',
    marginTop: '30px',
    border: '1px solid rgba(52, 152, 219, 0.1)',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.05)',
  },

  logTitle: {
    fontSize: '16px',
    fontWeight: '700',
    color: '#2d3e50',
    marginBottom: '18px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },

  logItem: {
    padding: '12px 14px',
    background: '#ffffff',
    borderLeft: '4px solid #3498db',
    borderRadius: '6px',
    marginBottom: '10px',
    fontSize: '14px',
    color: '#555555',
    transition: 'all 0.2s ease',
    boxShadow: '0 2px 6px rgba(0, 0, 0, 0.04)',
  },
  
  // Table
  tableWrapper: {
    borderRadius: '8px',
    overflow: 'hidden',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
  },
  
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    backgroundColor: '#ffffff',
  },
  
  tableHeader: {
    background: 'linear-gradient(135deg, #2d3e50 0%, #34495e 100%)',
    color: '#ffffff',
    padding: '18px 16px',
    textAlign: 'left',
    fontWeight: '700',
    fontSize: '13px',
    textTransform: 'uppercase',
    letterSpacing: '0.8px',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
  },
  
  tableCell: {
    padding: '16px 16px',
    borderBottom: '1px solid #ecf0f1',
    fontSize: '14px',
    color: '#555555',
    fontWeight: '500',
  },
  
  tableRowHover: {
    backgroundColor: '#f8f9fa',
    transition: 'all 0.2s ease',
  },
  
  // Empty state
  emptyState: {
    textAlign: 'center',
    padding: '60px 40px',
    color: '#999999',
  },
  
  emptyIcon: {
    fontSize: '48px',
    marginBottom: '16px',
  },
  
  emptyText: {
    fontSize: '15px',
  },
};

function FileUpload() {
  const [activeTab, setActiveTab] = useState('upload');
  const [designations, setDesignations] = useState('');
  const [location, setLocation] = useState('');
  const [numResults, setNumResults] = useState('');
  const [arrayInput, setArrayInput] = useState('');
  const [domains, setDomains] = useState('');
  const [overallProgress, setOverallProgress] = useState({ total: 0, processed: 0, remaining: 0 });
  const [progressUpdates, setProgressUpdates] = useState([]);
  const previewSet = useRef(new Set());
  const [previewData, setPreviewData] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStatus, setProcessingStatus] = useState('idle'); // 'idle', 'queued', 'processing', 'completed'
  const [currentDomain, setCurrentDomain] = useState('');
  const [downloadFileName, setDownloadFileName] = useState('');
  const [activityIndicator, setActivityIndicator] = useState(''); // For sidebar activity messages

  useEffect(() => {
    socket.on('connection_rejected', ({ message }) => {
      alert(message);
      socket.disconnect();
      window.close();
    });

    socket.on('process_data_response', (data) => {
      console.log('📨 process_data_response received:', data);

      // Check if this is the initial "job queued" response or final completion
      if (data.message && data.message.includes('queued')) {
        // Job is queued - keep processing active
        console.log('✅ Job queued, keeping processing active...');
        toast.info(`⏳ ${data.message}`);
        // Don't change isProcessing or processingStatus - keep them as is
      } else if (data.error) {
        // Error occurred
        toast.error(`❌ Error: ${data.message}`);
        setIsProcessing(false);
        setProcessingStatus('completed');
      } else {
        // Job actually completed with results
        console.log('✅ Job completed successfully!');
        toast.success(`✅ ${data.message}`);
        setIsProcessing(false);
        setProcessingStatus('completed');
      }
    });

    socket.on('refresh_response', (data) => {
      toast.info(data.message);
      setDesignations('');
      setLocation('');
      setNumResults('');
      setArrayInput('');
      setDomains('');
      setOverallProgress({ total: 0, processed: 0, remaining: 0 });
      setProgressUpdates([]);
      previewSet.current.clear();
      setPreviewData([]);
      setIsProcessing(false);
      setProcessingStatus('idle');
      setCurrentDomain('');
      setActivityIndicator('');
    });

    socket.on('overall_progress', (data) => {
      setOverallProgress({
        total: data.total,
        processed: data.processed,
        remaining: data.remaining,
      });
    });

    socket.on('progress_update', (data) => {
      setProgressUpdates((prev) => [...prev, `${data.domain}: ${data.message}`]);
      setCurrentDomain(data.domain);
      setProcessingStatus('processing');
      const msg = data.message;
      setActivityIndicator(`⟳ ${msg.length > 40 ? msg.substring(0, 40) + '...' : msg}`); // Show current activity in sidebar
      setIsProcessing(true); // Keep processing true while getting updates
    });

    socket.on('preview_data', (data) => {
      console.log('📊 Preview data received:', data);
      console.log('📊 Data type:', typeof data);
      console.log('📊 Data keys:', data ? Object.keys(data) : 'null');

      if (!data) {
        console.error('❌ Data is null or undefined');
        return;
      }

      const previewArray = data.previewData || data || [];
      console.log('✅ Preview array length:', previewArray.length);

      if (previewArray && previewArray.length > 0) {
        console.log('✅ Items received:', previewArray.length);
        console.log('📋 Sample item:', previewArray[0]);

        previewArray.forEach((item) => {
          const key = JSON.stringify(item);
          previewSet.current.add(key);
        });
      }

      const updatedPreviewData = Array.from(previewSet.current).map((str) => JSON.parse(str));
      console.log('🔄 Total preview data count:', updatedPreviewData.length);
      console.log('🔄 Updated data:', updatedPreviewData);
      setPreviewData(updatedPreviewData);
    });

    return () => {
      socket.off('connection_rejected');
      socket.off('process_data_response');
      socket.off('refresh_response');
      socket.off('overall_progress');
      socket.off('progress_update');
      socket.off('preview_data');
      console.log('🔌 Socket event listeners cleaned up');
    };
  }, []);

  const handleSubmit = () => {
    let parsedArray;
    try {
      parsedArray = JSON.parse(arrayInput || '[]');
    } catch {
      toast.error('Invalid JSON in array input');
      return;
    }

    // ✅ IMMEDIATE FEEDBACK
    setIsProcessing(true);
    setProcessingStatus('queued');
    setCurrentDomain('Initializing...');

    // ✅ SIDEBAR ACTIVITY INDICATOR - Display on LEFT with emoji
    setActivityIndicator('Processing queued...');

    // Show longer toast (5 seconds) so user sees it
    // toast.info('⏳ Extraction started! Processing request...', {
    //   autoClose: 5000,
    //   position: 'top-right',
    // });

    console.log('📤 Extraction started - Sending process_data to backend');

    socket.emit('process_data', {
      designations,
      location,
      numResults,
      arrayData: JSON.stringify(parsedArray),
      domains,
      downloadFileName,
    });
  };

  const handleRefresh = () => {
    socket.emit('refresh');
  };

  return (
    <div style={styles.container}>
      <ToastContainer position="top-right" autoClose={3000} />
      <style>{`
        * {
          font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
        }
        
        input:focus, textarea:focus {
          outline: none;
          border-color: #3498db !important;
          background-color: #ffffff !important;
          box-shadow: 0 0 0 4px rgba(52, 152, 219, 0.15), 0 4px 12px rgba(52, 152, 219, 0.15) !important;
        }
        
        button:hover:not(:disabled) {
          transform: translateY(-3px);
          box-shadow: 0 12px 28px rgba(0, 0, 0, 0.2) !important;
        }

        button:active:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15) !important;
        }
        
        table tbody tr {
          transition: all 0.2s ease;
        }

        table tbody tr:hover {
          background-color: #f5f7fa;
          box-shadow: inset 0 0 8px rgba(52, 152, 219, 0.1);
        }
        
        ul {
          list-style: none;
          padding: 0;
          margin: 0;
        }
        
        @keyframes blink {
          0%, 49% { opacity: 1; }
          50%, 100% { opacity: 0.3; }
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        ul li {
          padding: 12px 14px;
          background: #ffffff;
          border-left: 4px solid #3498db;
          border-radius: 6px;
          margin-bottom: 10px;
          font-size: 14px;
          color: #555555;
          transition: all 0.2s ease;
          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
          display: flex;
          align-items: center;
          gap: 6px;
        }

        ul li:hover {
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
          transform: translateX(2px);
        }
        
        ::-webkit-scrollbar {
          width: 8px;
        }
        
        ::-webkit-scrollbar-track {
          background: transparent;
        }
        
        ::-webkit-scrollbar-thumb {
          background: #cccccc;
          border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
          background: #999999;
        }
      `}</style>

      {/* Sidebar */}

      <div style={styles.sidebar}>
        <div style={styles.sidebarTitle}>
          <MdMailOutline size={28} />
          Email Extractor
        </div>

        <button
          onClick={() => setActiveTab('upload')}
          style={styles.navItem(activeTab === 'upload')}
        >
          <MdSettings size={20} />
          Configuration
        </button>

        <button
          onClick={() => setActiveTab('preview')}
          style={styles.navItem(activeTab === 'preview')}
        >
          <MdGridOn size={20} />
          Preview Data
        </button>

        {/* Stats in Sidebar */}
        <div style={styles.statsSection}>
          <div style={styles.statsLabel}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <MdStorage size={16} />
              Statistics
            </span>
          </div>
          
          <div style={styles.statItem}>
            <div style={styles.statValue}>{overallProgress.total}</div>
            <div style={styles.statName}>Total Domains</div>
          </div>
          
          <div style={styles.statItem}>
            <div style={styles.statValue}>{overallProgress.processed}</div>
            <div style={styles.statName}>Processed</div>
          </div>
          
          <div style={styles.statItem}>
            <div style={styles.statValue}>{overallProgress.remaining}</div>
            <div style={styles.statName}>Remaining</div>
          </div>

          <div style={{...styles.statItem, marginTop: '20px', background: isProcessing ? '#1a472a' : '#472a1a'}}>
            <div style={{...styles.statValue, color: isProcessing ? '#0059ff' : '#ff6b6b', fontSize: '14px'}}>
              {isProcessing ? '● Processing' : '○ Idle'}
            </div>
            <div style={{...styles.statName, color: isProcessing ? '#0059ff' : '#999999', marginTop: '8px'}}>
              {isProcessing ? (
                <>
                  <div style={{fontSize: '12px', marginBottom: '4px'}}>
                    Status: {processingStatus === 'queued' ? 'Queued' : processingStatus === 'processing' ? 'Extracting' : 'Completed'}
                  </div>
                  {currentDomain && (
                    <div style={{fontSize: '11px', wordBreak: 'break-word', maxHeight: '40px', overflow: 'hidden', marginBottom: '6px'}}>
                      Domain: {currentDomain}
                    </div>
                  )}
                  {activityIndicator && (
                    <div style={{
                      fontSize: '12px',
                      color: '#00ff00',
                      fontWeight: '600',
                      wordBreak: 'break-word',
                      maxHeight: '80px',
                      overflow: 'hidden',
                      borderTop: '2px solid #00ff00',
                      paddingTop: '8px',
                      marginTop: '8px',
                      animation: 'blink 1s infinite'
                    }}>
                      {activityIndicator}
                    </div>
                  )}
                </>
              ) : (
                'Ready'
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div style={styles.main}>
        {activeTab === 'upload' && (
          <>
            {/* Page Header */}
            {/* <div style={styles.pageHeader}>
              <h1 style={styles.pageTitle}>Configuration</h1>
              <p style={styles.pageSubtitle}>Set up your extraction parameters</p>
            </div> */}
              
            {/* Main Card */}
            <div style={styles.contentCard}>
              {/* Form Grid */}
              <div style={styles.formGrid}>
                {/* Domains */}
                <div style={{...styles.formField, ...styles.formGridFull}}>
                  <label style={{...styles.label, display: 'flex', alignItems: 'center', gap: '8px'}}>
                    <MdDomain size={16} />
                    Domains (one per line)
                  </label>
                  <textarea
                    placeholder="tatamotors.com&#10;zf.com&#10;microsoft.com"
                    value={domains}
                    onChange={(e) => setDomains(e.target.value)}
                    style={styles.textarea}
                    disabled={isProcessing}
                  />
                </div>

                {/* Designations */}
                <div style={styles.formField}>
                  <label style={{...styles.label, display: 'flex', alignItems: 'center', gap: '8px'}}>
                    <MdWorkHistory size={16} />
                    Job Designations
                  </label>
                  <input
                    type="text"
                    placeholder="manager1, developer2, sales5"
                    value={designations}
                    onChange={(e) => setDesignations(e.target.value)}
                    style={styles.input}
                    disabled={isProcessing}
                  />
                </div>

                {/* Locations */}
                <div style={styles.formField}>
                  <label style={{...styles.label, display: 'flex', alignItems: 'center', gap: '8px'}}>
                    <MdLocationOn size={16} />
                    Locations
                  </label>
                  <input
                    type="text"
                    placeholder="New York, San Francisco"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    style={styles.input}
                    disabled={isProcessing}
                  />
                </div>

                {/* Number of Results */}
                <div style={styles.formField}>
                  <label style={{...styles.label, display: 'flex', alignItems: 'center', gap: '8px'}}>
                    <MdNumbers size={16} />
                    Number of Emails
                  </label>
                  <input
                    type="number"
                    placeholder="50"
                    value={numResults}
                    onChange={(e) => setNumResults(e.target.value)}
                    style={styles.input}
                    disabled={isProcessing}
                  />
                </div>

                {/* <div style={{...styles.formField, ...styles.formGridFull}}> */}
                <div style={styles.formField}>
                  <label style={{...styles.label, display: 'flex', alignItems: 'center', gap: '8px'}}>
                    <MdSaveAlt size={16} />
                    Output File Name
                  </label>
                  <input
                    type="text"
                    placeholder="email_list"
                    value={downloadFileName}
                    onChange={(e) => setDownloadFileName(e.target.value)}
                    style={styles.input}
                    disabled={isProcessing}
                  />
                </div>

                {/* JSON Data */}
                <div style={{...styles.formField, ...styles.formGridFull}}>
                  <label style={{...styles.label, display: 'flex', alignItems: 'center', gap: '8px'}}>
                    <MdDataObject size={16} />
                    Additional JSON Data
                  </label>
                  <textarea
                    placeholder='{"department": "engineering"}'
                    value={arrayInput}
                    onChange={(e) => setArrayInput(e.target.value)}
                    style={{...styles.textarea, minHeight: '80px'}}
                    disabled={isProcessing}
                  />
                </div>

                {/* Output File Name */}
                
              </div>

              {/* Action Buttons */}
              <div style={styles.buttonGroup}>
                <button
                  onClick={handleSubmit}
                  style={styles.button('#3498db', isProcessing)}
                  disabled={isProcessing}
                >
                  <MdPlayCircle size={20} />
                  {isProcessing ? 'Processing...' : 'Start Extraction'}
                </button>
                <button
                  onClick={handleRefresh}
                  style={styles.button('#95a5a6', false)}
                >
                  <MdRefresh size={20} />
                  Reset Form
                </button>
              </div>

              {/* Activity Log */}
              <div style={styles.logSection}>
                <div style={{...styles.logTitle, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                  <span style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
                    <MdStorage size={18} />
                    Activity Log
                  </span>
                  {/* {isProcessing && (
                    <span style={{fontSize: '12px', color: '#3498db', animation: 'blink 1s infinite', display: 'flex', alignItems: 'center', gap: '4px'}}>
                      <MdAccessTime size={14} />
                      Live
                    </span>
                  )} */}
                </div>
                {progressUpdates.length === 0 ? (
                  <p style={{color: '#999999', fontSize: '14px', display: 'flex', alignItems: 'center', gap: '6px'}}>
                    {isProcessing ? (
                      <>
                        <MdAccessTime size={16} />
                        Processing...
                      </>
                    ) : (
                      'No updates yet. Start extraction to see progress....'
                    )}
                  </p>
                ) : (
                  <ul style={{maxHeight: '400px', overflowY: 'auto'}}>
                    {progressUpdates.map((u, i) => (
                      <li key={i} style={{color: u.includes('EMAIL FOUND') ? '#3498db' : '#666666'}}>
                        {u.includes('EMAIL FOUND') && <MdMailOutline size={14} style={{marginRight: '6px'}} />}
                        {u}
                      </li>
                    ))}
                    {isProcessing && progressUpdates.length > 0 && (
                      <li style={{color: '#e67e22', fontStyle: 'italic', display: 'flex', alignItems: 'center', gap: '6px'}}>
                        <MdAccessTime size={14} style={{animation: 'spin 1s linear infinite'}} />
                        Processing in progress...
                      </li>
                    )}
                  </ul>
                )}
              </div>
            </div>
          </>
        )}

        {activeTab === 'preview' && (
          <>
            {/* Preview Data Content */}
            <div style={styles.contentCard}>
              <div style={{marginBottom: '24px', paddingBottom: '20px', borderBottom: '2px solid rgba(52, 152, 219, 0.2)'}}>
                <h2 style={{fontSize: '24px', fontWeight: '700', color: '#2d3e50', display: 'flex', alignItems: 'center', gap: '12px', margin: 0}}>
                  <MdGridOn size={28} />
                  Extracted Data Preview
                </h2>
                <p style={{color: '#7f8c8d', fontSize: '14px', margin: '8px 0 0 0'}}>
                  Total Records: <strong style={{color: '#3498db', fontSize: '16px'}}>{previewData.length}</strong>
                </p>
              </div>

              {previewData.length === 0 ? (
                <div style={styles.emptyState}>
                  <div style={styles.emptyIcon}>📭</div>
                  <p style={styles.emptyText}>No data extracted yet. Start an extraction to see results here.</p>
                </div>
              ) : (
                <div style={styles.tableWrapper}>
                  <table style={styles.table}>
                    <thead>
                      <tr style={{background: 'linear-gradient(135deg, #2d3e50 0%, #34495e 100%)'}}>
                        <th style={{color: '#ffffff', padding: '18px 16px', textAlign: 'left', fontWeight: '700', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.8px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'}}>First Name</th>
                        <th style={{color: '#ffffff', padding: '18px 16px', textAlign: 'left', fontWeight: '700', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.8px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'}}>Job Title</th>
                        <th style={{color: '#ffffff', padding: '18px 16px', textAlign: 'left', fontWeight: '700', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.8px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'}}>Company</th>
                        <th style={{color: '#ffffff', padding: '18px 16px', textAlign: 'left', fontWeight: '700', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.8px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'}}>Location</th>
                        <th style={{color: '#ffffff', padding: '18px 16px', textAlign: 'left', fontWeight: '700', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.8px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'}}>Email</th>
                        <th style={{color: '#ffffff', padding: '18px 16px', textAlign: 'left', fontWeight: '700', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.8px', boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'}}>Domain</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previewData.map((item, index) => (
                        <tr key={index}>
                          <td style={styles.tableCell}>{item['First Name'] || '-'}</td>
                          <td style={styles.tableCell}>{item['job title'] || '-'}</td>
                          <td style={styles.tableCell}>{item.company || '-'}</td>
                          <td style={styles.tableCell}>{item.location || '-'}</td>
                          <td style={{...styles.tableCell, color: '#3498db', fontWeight: '600'}}>{item.email || '-'}</td>
                          <td style={styles.tableCell}>{item.domain || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}


export default FileUpload;
