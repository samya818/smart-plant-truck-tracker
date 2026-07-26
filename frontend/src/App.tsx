import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import Dashboard from '@/pages/Dashboard';
import MobilePage from '@/pages/MobilePage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-100">
        <nav className="bg-white shadow-sm p-4 flex gap-4">
          <Link to="/" className="text-blue-700 font-bold hover:underline">Dashboard</Link>
          <Link to="/mobile" className="text-blue-700 font-bold hover:underline">Interface Mobile</Link>
        </nav>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/mobile" element={<MobilePage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
