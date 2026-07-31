import "@fontsource-variable/geist-mono";
import "@fontsource-variable/nunito-sans";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router";
import { RootProvider } from "fumadocs-ui/provider/react-router";

import { DashboardAuthGate } from "@/components/dashboard/dashboard-auth";
import { DashboardRoutes } from "@/routes";
import "@/app/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter basename="/dashboard">
      <RootProvider
        search={{ enabled: false }}
        theme={{
          attribute: "class",
          defaultTheme: "system",
          enableSystem: true,
          disableTransitionOnChange: true,
        }}
      >
        <DashboardAuthGate>
          <DashboardRoutes />
        </DashboardAuthGate>
      </RootProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
