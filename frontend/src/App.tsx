import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import Ingest from "./pages/Ingest";
import KnowledgeMap from "./pages/KnowledgeMap";
import Gaps from "./pages/Gaps";
import Tutor from "./pages/Tutor";
import Memory from "./pages/Memory";
import Attention from "./pages/Attention";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Landing />} />
        <Route path="projects/:projectId">
          <Route index element={<Dashboard />} />
          <Route path="ingest" element={<Ingest />} />
          <Route path="map" element={<KnowledgeMap />} />
          <Route path="gaps" element={<Gaps />} />
          <Route path="attention" element={<Attention />} />
          <Route path="tutor" element={<Tutor />} />
          <Route path="memory" element={<Memory />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Route>
    </Routes>
  );
}
