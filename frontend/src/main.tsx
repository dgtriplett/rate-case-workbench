import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createRouter,
  RouterProvider,
  createRootRoute,
  createRoute,
  Outlet,
} from "@tanstack/react-router";

import App from "./App";
import "./styles/globals.css";

import CasesLanding from "./routes/CasesLanding";
import CaseShell from "./shell/CaseShell";
import AppShell from "./shell/AppShell";
import CaseHome from "./routes/case/Home";
import PhaseBoard from "./routes/case/PhaseBoard";
import DiscoveryInbox from "./routes/discovery/Inbox";
import Drafter from "./routes/discovery/Drafter";
import ReviewQueue from "./routes/discovery/ReviewQueue";
import TestimonyStudio from "./routes/testimony/Studio";
import KnowledgeLibrary from "./routes/knowledge/Library";
import WitnessCoordination from "./routes/witnesses/Coordination";
import FilingConsole from "./routes/filing/Console";
import ActivityAudit from "./routes/audit/Activity";
import RebuttalWorkbench from "./routes/rebuttal/Workbench";
import OrderRoute from "./routes/order/Order";
import PortfolioDashboard from "./routes/PortfolioDashboard";
import CaseCalendar from "./routes/case/Calendar";
import PositionsLedger from "./routes/case/PositionsLedger";
import CrossCaseInsights from "./routes/case/CrossCaseInsights";
import CompliancePage from "./routes/case/Compliance";
import HearingPrep from "./routes/case/HearingPrep";
import AdminAutomation from "./routes/admin/Automation";
import ApplicationWorkbench from "./routes/case/ApplicationWorkbench";
import Stakeholders from "./routes/case/Stakeholders";
import PublicCommentsPage from "./routes/case/PublicComments";
import AljRecommendation from "./routes/case/AljRecommendation";
import PublicNoticePage from "./routes/case/PublicNotice";
import SettlementsPage from "./routes/case/Settlements";
import OutboundDiscovery from "./routes/case/OutboundDiscovery";
import IntervenorTestimonyPage from "./routes/case/IntervenorTestimony";

import AdminShell from "./shell/AdminShell";
import AdminCases from "./routes/admin/Cases";
import AdminPhaseTemplates from "./routes/admin/PhaseTemplates";
import AdminUsers from "./routes/admin/Users";
import AdminModels from "./routes/admin/Models";
import AdminKnowledgeSources from "./routes/admin/KnowledgeSources";
import AdminGenie from "./routes/admin/Genie";
import AdminFeatureFlags from "./routes/admin/FeatureFlags";
import AdminIntegrations from "./routes/admin/Integrations";
import AdminAudit from "./routes/admin/Audit";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

// --- routes ----------------------------------------------------------------

const rootRoute = createRootRoute({
  component: () => (
    <App>
      <Outlet />
    </App>
  ),
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: CasesLanding,
});

const caseRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "cases/$caseId",
  component: CaseShell,
});

const caseIndexRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "/",
  component: CaseHome,
});

const caseBoardRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "board",
  component: PhaseBoard,
});

const caseDiscoveryRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "discovery",
  component: DiscoveryInbox,
});

const caseDrafterRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "discovery/$drId",
  component: Drafter,
});

const caseReviewRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "review",
  component: ReviewQueue,
});

const caseTestimonyRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "testimony",
  component: TestimonyStudio,
});

const caseKnowledgeRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "knowledge",
  component: KnowledgeLibrary,
});

const caseWitnessesRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "witnesses",
  component: WitnessCoordination,
});

const caseFilingRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "filing",
  component: FilingConsole,
});

const caseActivityRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "activity",
  component: ActivityAudit,
});

const caseRebuttalRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "rebuttal",
  component: RebuttalWorkbench,
});

const caseOrderRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "order",
  component: OrderRoute,
});

const caseCalendarRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "calendar",
  component: CaseCalendar,
});

const casePositionsLedgerRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "positions-ledger",
  component: PositionsLedger,
});

const caseCrossCaseRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "cross-case",
  component: CrossCaseInsights,
});

const caseComplianceRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "compliance",
  component: CompliancePage,
});

const caseHearingPrepRoute = createRoute({
  getParentRoute: () => caseRoute,
  path: "hearing-prep",
  component: HearingPrep,
});

const caseAppWorkbenchRoute = createRoute({
  getParentRoute: () => caseRoute, path: "application-workbench", component: ApplicationWorkbench,
});
const caseStakeholdersRoute = createRoute({
  getParentRoute: () => caseRoute, path: "stakeholders", component: Stakeholders,
});
const casePublicCommentsRoute = createRoute({
  getParentRoute: () => caseRoute, path: "public-comments", component: PublicCommentsPage,
});
const caseAljRoute = createRoute({
  getParentRoute: () => caseRoute, path: "alj-recommendation", component: AljRecommendation,
});
const casePublicNoticeRoute = createRoute({
  getParentRoute: () => caseRoute, path: "public-notice", component: PublicNoticePage,
});
const caseSettlementsRoute = createRoute({
  getParentRoute: () => caseRoute, path: "settlements", component: SettlementsPage,
});
const caseOutboundDiscoveryRoute = createRoute({
  getParentRoute: () => caseRoute, path: "discovery-outbound", component: OutboundDiscovery,
});
const caseIntervenorTestimonyRoute = createRoute({
  getParentRoute: () => caseRoute, path: "intervenor-testimony", component: IntervenorTestimonyPage,
});

const portfolioRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "portfolio",
  component: () => (
    <AppShell><PortfolioDashboard /></AppShell>
  ),
});

const adminRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "admin",
  component: AdminShell,
});

const adminIndexRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "/",
  component: AdminCases,
});

const adminCasesRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "cases",
  component: AdminCases,
});
const adminPhaseTemplatesRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "phase-templates",
  component: AdminPhaseTemplates,
});
const adminUsersRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "users",
  component: AdminUsers,
});
const adminModelsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "models",
  component: AdminModels,
});
const adminKnowledgeSourcesRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "knowledge-sources",
  component: AdminKnowledgeSources,
});
const adminGenieRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "genie",
  component: AdminGenie,
});
const adminFeatureFlagsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "feature-flags",
  component: AdminFeatureFlags,
});
const adminIntegrationsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "integrations",
  component: AdminIntegrations,
});
const adminAuditRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "audit",
  component: AdminAudit,
});
const adminAutomationRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "automation",
  component: AdminAutomation,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  portfolioRoute,
  caseRoute.addChildren([
    caseIndexRoute,
    caseBoardRoute,
    caseDiscoveryRoute,
    caseDrafterRoute,
    caseReviewRoute,
    caseTestimonyRoute,
    caseKnowledgeRoute,
    caseWitnessesRoute,
    caseFilingRoute,
    caseActivityRoute,
    caseRebuttalRoute,
    caseOrderRoute,
    caseCalendarRoute,
    casePositionsLedgerRoute,
    caseCrossCaseRoute,
    caseComplianceRoute,
    caseHearingPrepRoute,
    caseAppWorkbenchRoute,
    caseStakeholdersRoute,
    casePublicCommentsRoute,
    caseAljRoute,
    casePublicNoticeRoute,
    caseSettlementsRoute,
    caseOutboundDiscoveryRoute,
    caseIntervenorTestimonyRoute,
  ]),
  adminRoute.addChildren([
    adminIndexRoute,
    adminCasesRoute,
    adminPhaseTemplatesRoute,
    adminUsersRoute,
    adminModelsRoute,
    adminKnowledgeSourcesRoute,
    adminGenieRoute,
    adminFeatureFlagsRoute,
    adminIntegrationsRoute,
    adminAuditRoute,
    adminAutomationRoute,
  ]),
]);

const router = createRouter({
  routeTree,
  defaultPreload: "intent",
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
