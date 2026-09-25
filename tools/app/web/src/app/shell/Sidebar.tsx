import {
  LayoutDashboard, Kanban, FileText, FileInput, ClipboardCheck, ShieldCheck,
  PackageOpen, GitCompare, Activity, Network, Settings, Inbox, FolderOpen,
} from 'lucide-react'
import type { View } from './routes'

const GROUPS: { label: string; items: { label: string; view: View; icon: React.ReactNode }[] }[] = [
  // The file-directory Explore is the approved PRIMARY surface (see
  // .superpowers/brainstorm/2202-1786328379/content/full-review.html) — it
  // leads the sidebar, above every other project nav item.
  { label: 'Browse', items: [
    { label: 'Explore', view: { kind: 'explore' }, icon: <FolderOpen size={17} /> },
  ] },
  { label: 'Global', items: [
    { label: 'Inbox', view: { kind: 'inbox' }, icon: <Inbox size={17} /> },
  ] },
  { label: 'Plan', items: [
    { label: 'Dashboard', view: { kind: 'dashboard' }, icon: <LayoutDashboard size={17} /> },
    { label: 'Board', view: { kind: 'board' }, icon: <Kanban size={17} /> },
    { label: 'Stories', view: { kind: 'stories' }, icon: <FileText size={17} /> },
  ] },
  { label: 'Ingest', items: [
    { label: 'Documents', view: { kind: 'documents' }, icon: <FileInput size={17} /> },
  ] },
  { label: 'Generation', items: [
    { label: 'Test Cases', view: { kind: 'testcases' }, icon: <ClipboardCheck size={17} /> },
    { label: 'Coverage', view: { kind: 'coverage' }, icon: <ShieldCheck size={17} /> },
    { label: 'Suites & Export', view: { kind: 'suites' }, icon: <PackageOpen size={17} /> },
  ] },
  { label: 'Maintain', items: [
    { label: 'Changes & Impact', view: { kind: 'changes' }, icon: <GitCompare size={17} /> },
    { label: 'Activity', view: { kind: 'activity' }, icon: <Activity size={17} /> },
  ] },
  { label: 'Trace', items: [
    { label: 'Traceability', view: { kind: 'rtm' }, icon: <Network size={17} /> },
    { label: 'Settings', view: { kind: 'settings' }, icon: <Settings size={17} /> },
  ] },
]

export function Sidebar({ active, onNavigate, project }: {
  active: View
  onNavigate: (v: View) => void
  project?: string
}) {
  // Jira-style project header: square avatar + name + project-type subtitle
  // (the global brand lives in the top bar).
  const name = project || 'tc-copilot'
  return (
    <>
      <div className="proj-head-nav">
        <span className="proj-av" aria-hidden>{name.slice(0, 2).toUpperCase()}</span>
        <span className="who"><b>{name}</b><span>Operator project</span></span>
      </div>
      {GROUPS.map((g) => (
        <div key={g.label} className="nav-group">
          <div className="lbl">{g.label}</div>
          <nav className="nav">
            {g.items.map((it) => (
              <button
                key={it.label}
                aria-current={it.view.kind === active.kind ? 'page' : undefined}
                onClick={() => onNavigate(it.view)}
              >
                {it.icon}{it.label}
              </button>
            ))}
          </nav>
        </div>
      ))}
      <div className="spacer" />
      <div className="operator"><span className="av">SY</span><span className="who"><b>syabz</b><span>operator</span></span></div>
    </>
  )
}
