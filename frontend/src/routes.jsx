import { Route, Routes } from 'react-router-dom';

import HomePage from './features/home/HomePage';

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
    </Routes>
  );
}
