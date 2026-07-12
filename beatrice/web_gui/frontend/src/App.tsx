import React, { useEffect, useRef, useState } from 'react';
import { WsClient } from './api/websocket';
import { GraphStore } from './store/graphStore';
import { Layout } from './components/Layout';
import { GraphStoreContext } from './store/context';
import { FileInfo } from './api/types';

const WS_URL = `ws://${window.location.hostname}:8576/ws`;

const App: React.FC = () => {
  const wsRef = useRef<WsClient | null>(null);
  const storeRef = useRef<GraphStore | null>(null);
  const [ready, setReady] = useState(false);
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ws = new WsClient();
    wsRef.current = ws;
    ws.onStatusChange = (connected) => {
      if (connected) {
        // Get file info
        ws.call<FileInfo>('get_file_info')
          .then((info) => {
            setFileInfo(info);
            const store = new GraphStore(ws);
            storeRef.current = store;
            return store.init(info.path);
          })
          .then(() => setReady(true))
          .catch((e) => setError(`Ошибка: ${e.message}`));
      }
    };
    ws.connect(WS_URL);
    return () => {
      ws.disconnect();
    };
  }, []);

  if (error) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', background: '#1a1a2e', color: '#e94560',
        fontFamily: 'sans-serif', fontSize: 18, flexDirection: 'column',
        gap: 16,
      }}>
        <div style={{ fontSize: 48 }}>⚠️</div>
        <div>{error}</div>
      </div>
    );
  }

  if (!ready || !storeRef.current) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', background: '#1a1a2e', color: '#eee',
        fontFamily: 'sans-serif', fontSize: 18,
      }}>
        Подключение к серверу...
    </div>
    );
  }

  return (
    <GraphStoreContext.Provider value={storeRef.current}>
      <Layout />
    </GraphStoreContext.Provider>
  );
};

export default App;
