import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { Shell } from "@/components/Shell";
import { useAuth } from "@/context/Auth";
import { CampaignsPage } from "@/pages/Campaigns";
import { ClipPage } from "@/pages/Clip";
import { FeedPage } from "@/pages/Feed";
import { InboxPage } from "@/pages/Inbox";
import { LabPage } from "@/pages/Lab";
import { LoginPage } from "@/pages/Login";
import { ProfilePage } from "@/pages/Profile";
import { UploadPage } from "@/pages/Upload";

function Guard({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/entrar" replace />;
  return children;
}

export function App() {
  return (
    <Routes>
      <Route path="/entrar" element={<LoginPage />} />
      <Route
        element={
          <Guard>
            <Shell />
          </Guard>
        }
      >
        <Route path="/" element={<FeedPage />} />
        <Route path="/siguiendo" element={<FeedPage initialLane="following" showLanes={false} />} />
        <Route path="/amigos" element={<FeedPage initialLane="friends" showLanes={false} />} />
        <Route path="/clip/:id" element={<ClipPage />} />
        <Route path="/bandeja" element={<InboxPage />} />
        <Route path="/yo" element={<ProfilePage />} />
        <Route path="/lab" element={<LabPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/anuncios" element={<CampaignsPage />} />
        <Route path="/campaigns" element={<Navigate to="/anuncios" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
