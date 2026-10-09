import React, { useState, useEffect, useMemo, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './index.css';
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';

const API = import.meta.env.VITE_API_URL || (
  window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000'
    : 'https://gold-ai-predictor.onrender.com'
);

const fmt = (v, d = 2) => {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  const num = Number(v);
  return num.toLocaleString('en-US', {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
};

export default function App() {
  const [data, setData] = useState(null);
  const [asset, setAsset] = useState('sjc');
  const [chartType, setChartType] = useState('line');
  const [selectedWeek, setSelectedWeek] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [messages, setMessages] = useState([
    {
      sender: 'ai',
      text: 'Xin chào! Mình là trợ lý phân tích thị trường Smart Gold AI. Bạn cần xem xu hướng giá hay tư vấn thông tin gì hôm nay?'
    },
  ]);
  const [inputMsg, setInputMsg] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

  const fetchData = async (weekNum = selectedWeek) => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await fetch(`${API}/api/predict?week=${weekNum}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const result = await res.json();
      setData(result);

      if (result?.ai_analysis) {
        setMessages((prev) => {
          const exists = prev.some((m) => m.text === result.ai_analysis);
          if (exists) return prev;
          return [...prev, { sender: 'ai', text: result.ai_analysis }];
        });
      }
    } catch (err) {
      console.error('Lỗi kết nối backend:', err);
      setLoadError('Chưa thể kết nối tới máy chủ dữ liệu. Vui lòng kiểm tra lại dịch vụ Backend.');
    } finally {
      setLoading(false);
    }
  };

useEffect(() => { 
    if (messages.length > 1) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); 
    }
  }, [messages]);

  const handleWeekChange = (e) => {
    setSelectedWeek(Number(e.target.value));
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!inputMsg.trim() || chatLoading) return;
    const userText = inputMsg.trim();
    setMessages((prev) => [...prev, { sender: 'user', text: userText }]);
    setInputMsg('');
    setChatLoading(true);
    try {
      const res = await fetch(`${API}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userText }),
      });
      const resData = await res.json();
      setMessages((prev) => [...prev, { sender: 'ai', text: resData.reply || 'Hiện tại chưa thể phản hồi, vui lòng thử lại sau.' }]);
    } catch {
      setMessages((prev) => [...prev, { sender: 'ai', text: 'Không thể kết nối với trợ lý Smart Gold AI lúc này.' }]);
    } finally {
      setChatLoading(false);
    }
  };

  const history = data?.historical_data || [];
  const predictions = data?.predictions || [];

  // Lấy bản ghi giá SJC gần nhất trong lịch sử nếu cào thực tế hôm nay bị null
  const lastHistoryWithSjc = [...history].reverse().find(h => h.sjc_sell !== null && h.sjc_sell !== undefined);

  const cur = {
    sjc_buy: data?.current_data?.sjc_buy ?? lastHistoryWithSjc?.sjc_buy,
    sjc_sell: data?.current_data?.sjc_sell ?? lastHistoryWithSjc?.sjc_sell,
    world_price: data?.current_data?.world_price ?? lastHistoryWithSjc?.world_price,
  };

  // TỔNG HỢP DỮ LIỆU VẼ BIỂU ĐỒ
  const chartData = useMemo(() => {
    const list = [];

    // 1. Dữ liệu lịch sử tuần đã chọn
    history.forEach((h) => {
      const actualVal = asset === 'sjc' ? h.sjc_sell : h.world_price;
      const predVal = asset === 'sjc' ? h.sjc_predict_sell : h.world_predict;

      list.push({
        date: h.date ? h.date.slice(5) : '',
        actual: actualVal ?? null,
        predict: predVal ?? null,
      });
    });

    // 2. Dự báo tương lai (Chỉ khi xem Tuần 1)
    if (selectedWeek === 1 && predictions.length > 0) {
      if (list.length > 0) {
        const lastIndexWithActual = [...list].reverse().findIndex(x => x.actual !== null);
        if (lastIndexWithActual !== -1) {
          const idx = list.length - 1 - lastIndexWithActual;
          list[idx].predict = list[idx].actual;
        }
      }

      predictions.forEach((p) => {
        const val = asset === 'sjc' ? p.sjc_predict_sell : p.world_predict;
        list.push({
          date: p.date ? p.date.slice(5) : '',
          actual: null,
          predict: val ?? null,
        });
      });
    }

    return list;
  }, [history, predictions, asset, selectedWeek]);

  const isSJC = asset === 'sjc';
  const themeColor = isSJC ? '#d97706' : '#2563eb';
  const predictColor = '#10b981';
  const unitText = isSJC ? 'triệu VNĐ/lượng' : 'USD/ounce';

  return (
    <div style={styles.appContainer}>
      <header style={styles.appBar}>
        <div style={styles.appBarInner}>
          <div style={styles.brand}>
            <div style={styles.logoBadge}>✨</div>
            <div>
              <h1 style={styles.appTitle}>Smart Gold AI</h1>
              <p style={styles.appSubTitle}>Dữ liệu cào thực tế & Dự báo giá vàng thông minh</p>
            </div>
          </div>
          <button onClick={() => fetchData(selectedWeek)} style={styles.refreshBtn}>
            🔄 Cập nhật
          </button>
        </div>
      </header>

      <main style={styles.mainContent}>
        {loadError && <div style={styles.alertError}>{loadError}</div>}

        <section style={styles.grid3}>
          <div style={styles.metricCard}>
            <div style={styles.metricHeader}>
              <span style={styles.metricTitle}>Vàng SJC (Mua vào)</span>
              <span style={styles.badgeSuccess}>Trong nước</span>
            </div>
            <div style={{ ...styles.metricValue, color: '#059669' }}>
              {loading ? '...' : fmt(cur.sjc_buy, 2)}
              <span style={styles.metricUnit}> triệu/lượng</span>
            </div>
          </div>

          <div style={styles.metricCard}>
            <div style={styles.metricHeader}>
              <span style={styles.metricTitle}>Vàng SJC (Bán ra)</span>
              <span style={styles.badgeDanger}>Trong nước</span>
            </div>
            <div style={{ ...styles.metricValue, color: '#dc2626' }}>
              {loading ? '...' : fmt(cur.sjc_sell, 2)}
              <span style={styles.metricUnit}> triệu/lượng</span>
            </div>
          </div>

          <div style={styles.metricCard}>
            <div style={styles.metricHeader}>
              <span style={styles.metricTitle}>Vàng Thế Giới (XAU/USD)</span>
              <span style={styles.badgeInfo}>Quốc tế</span>
            </div>
            <div style={{ ...styles.metricValue, color: '#2563eb' }}>
              {loading ? '...' : `$${fmt(cur.world_price, 2)}`}
              <span style={styles.metricUnit}> / ounce</span>
            </div>
          </div>
        </section>

        {/* BIỂU ĐỒ VỚI MENU CHỌN 4 TUẦN */}
        <section style={styles.card}>
          <div style={styles.cardHeader}>
            <div>
              <h2 style={styles.cardTitle}>
                Xu hướng {isSJC ? 'SJC' : 'Thế giới'} - {selectedWeek === 1 ? 'Tuần hiện tại & Dự báo' : `Đối chiếu Tuần ${selectedWeek}`}
              </h2>
              <p style={styles.cardSub}>Đối chiếu dữ liệu cào thực tế và mô hình dự báo AI</p>
            </div>

            <div style={styles.controlsRow}>
              <select value={selectedWeek} onChange={handleWeekChange} style={styles.selectWeek}>
                <option value={1}>📅 Tuần 1 (Hiện tại & 7 ngày tới)</option>
                <option value={2}>⏮️ Tuần 2 (Đối chiếu tuần trước)</option>
                <option value={3}>⏮️ Tuần 3 (Đối chiếu 2 tuần trước)</option>
                <option value={4}>⏮️ Tuần 4 (Đối chiếu 3 tuần trước)</option>
              </select>

              <div style={styles.segmentedControl}>
                <button
                  style={asset === 'sjc' ? styles.segmentActive : styles.segmentBtn}
                  onClick={() => setAsset('sjc')}
                >
                  SJC
                </button>
                <button
                  style={asset === 'world' ? styles.segmentActive : styles.segmentBtn}
                  onClick={() => setAsset('world')}
                >
                  Thế giới
                </button>
              </div>

              <div style={styles.segmentedControl}>
                <button
                  style={chartType === 'line' ? styles.segmentActive : styles.segmentBtn}
                  onClick={() => setChartType('line')}
                >
                  Đường
                </button>
                <button
                  style={chartType === 'area' ? styles.segmentActive : styles.segmentBtn}
                  onClick={() => setChartType('area')}
                >
                  Miền
                </button>
                <button
                  style={chartType === 'bar' ? styles.segmentActive : styles.segmentBtn}
                  onClick={() => setChartType('bar')}
                >
                  Cột
                </button>
              </div>
            </div>
          </div>

          <div style={styles.chartContainer}>
            {loading ? (
              <div style={styles.centeredState}>Đang tải dữ liệu thực tế...</div>
            ) : chartData.length === 0 ? (
              <div style={styles.centeredState}>Chưa có dữ liệu cho tuần đã chọn.</div>
            ) : (
              <ResponsiveContainer width="100%" height={320}>
                {chartType === 'line' ? (
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                    <YAxis domain={['auto', 'auto']} stroke="#94a3b8" tick={{ fontSize: 12 }} width={65} />
                    <Tooltip formatter={(val, name) => [fmt(val, 2) + ' ' + unitText, name === 'actual' ? 'Giá Thật' : 'Dự Báo AI']} />
                    <Legend verticalAlign="top" height={36} />
                    <Line type="monotone" dataKey="actual" name="Giá Thật (Cào)" stroke={themeColor} strokeWidth={2.5} dot={{ r: 4 }} connectNulls />
                    <Line type="monotone" dataKey="predict" name="Giá Dự Báo AI" stroke={predictColor} strokeWidth={2} strokeDasharray="4 4" dot={{ r: 3 }} connectNulls />
                  </LineChart>
                ) : chartType === 'area' ? (
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="colorActual" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={themeColor} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={themeColor} stopOpacity={0.0} />
                      </linearGradient>
                      <linearGradient id="colorPred" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={predictColor} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={predictColor} stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                    <YAxis domain={['auto', 'auto']} stroke="#94a3b8" tick={{ fontSize: 12 }} width={65} />
                    <Tooltip formatter={(val, name) => [fmt(val, 2) + ' ' + unitText, name === 'actual' ? 'Giá Thật' : 'Dự Báo AI']} />
                    <Legend verticalAlign="top" height={36} />
                    <Area type="monotone" dataKey="actual" name="Giá Thật (Cào)" stroke={themeColor} fillOpacity={1} fill="url(#colorActual)" strokeWidth={2} connectNulls />
                    <Area type="monotone" dataKey="predict" name="Giá Dự Báo AI" stroke={predictColor} strokeDasharray="4 4" fillOpacity={1} fill="url(#colorPred)" strokeWidth={2} connectNulls />
                  </AreaChart>
                ) : (
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                    <YAxis domain={['auto', 'auto']} stroke="#94a3b8" tick={{ fontSize: 12 }} width={65} />
                    <Tooltip formatter={(val, name) => [fmt(val, 2) + ' ' + unitText, name === 'actual' ? 'Giá Thật' : 'Dự Báo AI']} />
                    <Legend verticalAlign="top" height={36} />
                    <Bar dataKey="actual" name="Giá Thật (Cào)" fill={themeColor} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="predict" name="Giá Dự Báo AI" fill={predictColor} radius={[4, 4, 0, 0]} />
                  </BarChart>
                )}
              </ResponsiveContainer>
            )}
          </div>
          <div style={styles.chartFooterNote}>
            💡 Đường màu nổi biểu thị **Giá Thật**, đường nét đứt biểu thị **Dự Báo AI** (Lưu vết để kiểm tra độ chính xác).
          </div>
        </section>

        {/* BẢNG ĐỐI CHIẾU DỮ LIỆU CÀO VÀ DỰ BÁO */}
        <section style={styles.card}>
          <div style={styles.cardHeader}>
            <div>
              <h2 style={styles.cardTitle}>Lịch Sử & Đối Chiếu Giá - Tuần {selectedWeek}</h2>
              <p style={styles.cardSub}>So sánh giá thực tế lưu kho với giá dự đoán trước đó</p>
            </div>
          </div>

          <div style={styles.tableWrapper}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Ngày</th>
                  <th style={styles.th}>SJC Thật (Bán)</th>
                  <th style={styles.th}>SJC AI Dự Đoán</th>
                  <th style={styles.th}>Thế Giới Thật</th>
                  <th style={styles.th}>Thế Giới AI Dự Đoán</th>
                </tr>
              </thead>
              <tbody>
                {history.length > 0 ? (
                  history.map((row, idx) => (
                    <tr key={idx} style={styles.tr}>
                      <td style={styles.tdBold}>{row.date}</td>
                      <td style={{ ...styles.td, color: '#dc2626', fontWeight: '600' }}>
                        {fmt(row.sjc_sell, 2)} tr
                      </td>
                      <td style={{ ...styles.td, color: '#059669' }}>
                        {fmt(row.sjc_predict_sell, 2)} tr
                      </td>
                      <td style={{ ...styles.td, color: '#2563eb', fontWeight: '600' }}>
                        ${fmt(row.world_price, 2)}
                      </td>
                      <td style={{ ...styles.td, color: '#059669' }}>
                        ${fmt(row.world_predict, 2)}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="5" style={styles.centeredState}>Chưa có bản ghi dữ liệu cho tuần này.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* CHAT SMART GOLD AI */}
        <section style={styles.card}>
          <div style={styles.cardHeader}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={styles.aiAvatar}>AI</div>
              <div>
                <h2 style={styles.cardTitle}>Trợ lý Phân tích Smart Gold AI</h2>
                <p style={styles.cardSub}>Tư vấn chiến lược mua bán vàng theo tuần</p>
              </div>
            </div>
          </div>

          <div style={styles.chatWindow}>
            {messages.map((m, i) => (
              <div
                key={i}
                style={m.sender === 'user' ? styles.userBubbleWrap : styles.aiBubbleWrap}
              >
                <div style={m.sender === 'user' ? styles.userBubble : styles.aiBubble}>
                  {m.sender === 'ai' ? (
                    <div className="markdown-content">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {m.text}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    m.text
                  )}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div style={styles.aiBubbleWrap}>
                <div style={styles.aiBubbleLoading}>Trợ lý Smart Gold AI đang phân tích dữ liệu...</div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <form onSubmit={handleSend} style={styles.chatForm}>
            <input
              type="text"
              placeholder="Hỏi Smart Gold AI (ví dụ: So sánh sai số dự báo tuần này?)..."
              value={inputMsg}
              onChange={(e) => setInputMsg(e.target.value)}
              disabled={chatLoading}
              style={styles.chatInput}
            />
            <button type="submit" disabled={chatLoading} style={styles.sendButton}>
              Gửi
            </button>
          </form>
        </section>
      </main>
    </div>
  );
}

const styles = {
  appContainer: {
    backgroundColor: '#f8fafc',
    color: '#0f172a',
    minHeight: '100vh',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    paddingBottom: 40,
  },
  appBar: {
    backgroundColor: '#ffffff',
    borderBottom: '1px solid #e2e8f0',
    position: 'sticky',
    top: 0,
    zIndex: 10,
  },
  appBarInner: {
    maxWidth: 1000,
    margin: '0 auto',
    padding: '12px 20px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  brand: { display: 'flex', alignItems: 'center', gap: 12 },
  logoBadge: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: '#fef3c7',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 18,
  },
  appTitle: { margin: 0, fontSize: 17, fontWeight: '700', color: '#0f172a' },
  appSubTitle: { margin: 0, fontSize: 12, color: '#64748b' },
  refreshBtn: {
    backgroundColor: '#f1f5f9',
    border: 'none',
    padding: '8px 14px',
    borderRadius: 8,
    fontSize: 13,
    fontWeight: '600',
    color: '#334155',
    cursor: 'pointer',
  },
  mainContent: {
    maxWidth: 1000,
    margin: '20px auto 0',
    padding: '0 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
  },
  alertError: {
    backgroundColor: '#fef2f2',
    color: '#991b1b',
    border: '1px solid #fecaca',
    padding: '12px 16px',
    borderRadius: 10,
    fontSize: 13,
  },
  grid3: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
    gap: 16,
  },
  metricCard: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    padding: 16,
    border: '1px solid #e2e8f0',
    boxShadow: '0 1px 2px rgba(0, 0, 0, 0.03)',
  },
  metricHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  metricTitle: { fontSize: 13, color: '#64748b', fontWeight: '500' },
  badgeSuccess: { backgroundColor: '#dcfce7', color: '#15803d', fontSize: 11, padding: '2px 8px', borderRadius: 12, fontWeight: '600' },
  badgeDanger: { backgroundColor: '#fee2e2', color: '#b91c1c', fontSize: 11, padding: '2px 8px', borderRadius: 12, fontWeight: '600' },
  badgeInfo: { backgroundColor: '#dbeafe', color: '#1d4ed8', fontSize: 11, padding: '2px 8px', borderRadius: 12, fontWeight: '600' },
  metricValue: { fontSize: 24, fontWeight: '700' },
  metricUnit: { fontSize: 13, color: '#64748b', fontWeight: '400' },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    border: '1px solid #e2e8f0',
    padding: 20,
    boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 16,
  },
  cardTitle: { margin: 0, fontSize: 16, fontWeight: '700', color: '#0f172a' },
  cardSub: { margin: '2px 0 0', fontSize: 12, color: '#64748b' },
  controlsRow: { display: 'flex', gap: 10, flexWrap: 'wrap' },
  selectWeek: {
    backgroundColor: '#ffffff',
    border: '1px solid #cbd5e1',
    borderRadius: 8,
    padding: '5px 10px',
    fontSize: 12,
    fontWeight: '600',
    color: '#0f172a',
    cursor: 'pointer',
    outline: 'none',
  },
  segmentedControl: {
    backgroundColor: '#f1f5f9',
    padding: 3,
    borderRadius: 8,
    display: 'flex',
    gap: 2,
  },
  segmentBtn: {
    border: 'none',
    backgroundColor: 'transparent',
    padding: '5px 12px',
    borderRadius: 6,
    fontSize: 12,
    fontWeight: '600',
    color: '#64748b',
    cursor: 'pointer',
  },
  segmentActive: {
    border: 'none',
    backgroundColor: '#ffffff',
    padding: '5px 12px',
    borderRadius: 6,
    fontSize: 12,
    fontWeight: '700',
    color: '#0f172a',
    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
    cursor: 'pointer',
  },
  chartContainer: { width: '100%', minHeight: 320 },
  chartFooterNote: { marginTop: 12, fontSize: 12, color: '#94a3b8', textAlign: 'right' },
  centeredState: { padding: '40px 0', textAlign: 'center', color: '#94a3b8', fontSize: 13 },
  tableWrapper: { overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 },
  th: { padding: '10px 12px', borderBottom: '1px solid #e2e8f0', color: '#64748b', fontWeight: '600' },
  tr: { borderBottom: '1px solid #f8fafc' },
  td: { padding: '12px' },
  tdBold: { padding: '12px', fontWeight: '600', color: '#334155' },
  aiAvatar: {
    width: 32,
    height: 32,
    borderRadius: '50%',
    backgroundColor: '#4f46e5',
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 12,
    fontWeight: 'bold',
  },
  chatWindow: {
    height: 380,
    overflowY: 'auto',
    backgroundColor: '#f8fafc',
    borderRadius: 10,
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  userBubbleWrap: { display: 'flex', justifyContent: 'flex-end', width: '100%' },
  aiBubbleWrap: { display: 'flex', justifyContent: 'flex-start', width: '100%' },
  userBubble: {
    backgroundColor: '#2563eb',
    color: '#ffffff',
    padding: '10px 14px',
    borderRadius: '14px 14px 2px 14px',
    fontSize: 13,
    maxWidth: '85%',
    lineHeight: 1.5,
  },
  aiBubble: {
    backgroundColor: '#ffffff',
    color: '#1e293b',
    border: '1px solid #e2e8f0',
    padding: '14px 18px',
    borderRadius: '14px 14px 14px 2px',
    fontSize: 13,
    width: '100%',
    maxWidth: '100%',
    boxSizing: 'border-box',
    lineHeight: 1.6,
    boxShadow: '0 1px 2px rgba(0,0,0,0.02)',
    overflowX: 'auto',
  },
  aiBubbleLoading: {
    backgroundColor: '#ffffff',
    color: '#94a3b8',
    border: '1px solid #e2e8f0',
    padding: '8px 12px',
    borderRadius: 12,
    fontSize: 12,
    fontStyle: 'italic',
  },
  chatForm: { marginTop: 12, display: 'flex', gap: 8 },
  chatInput: {
    flex: 1,
    border: '1px solid #cbd5e1',
    borderRadius: 8,
    padding: '10px 14px',
    fontSize: 13,
    outline: 'none',
  },
  sendButton: {
    backgroundColor: '#0f172a',
    color: '#ffffff',
    border: 'none',
    borderRadius: 8,
    padding: '0 18px',
    fontSize: 13,
    fontWeight: '600',
    cursor: 'pointer',
  },
};