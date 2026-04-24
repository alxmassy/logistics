import { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MapPage from '@/pages/MapPage';
import AnalyticsPage from '@/pages/AnalyticsPage';
import { getSocket, disconnectSocket } from '@/lib/socket';

/**
 * Root application with routing.
 *
 * Routes:
 *   /           → MapPage (full-screen map + decision sidebar)
 *   /analytics  → AnalyticsPage (event log, system health, pipeline analytics)
 */
export default function App() {
  // Initialize socket connection on mount (shared across all pages)
  useEffect(() => {
    const socket = getSocket();
    return () => {
      disconnectSocket();
    };
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MapPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
      </Routes>
    </BrowserRouter>
  );
}
