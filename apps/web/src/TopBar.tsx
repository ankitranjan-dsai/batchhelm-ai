import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Bell,
  CheckCheck,
  ChevronDown,
  LogOut,
  Search,
  Settings,
  UserRound,
} from "lucide-react";
import { ProviderEvidenceControl } from "./ProviderEvidenceControl";
import type { ProviderProofState, ProviderStatus, QwenVerificationReceipt } from "./api";
import type { RecallIncident, StaffTask } from "./types";
import { clearDemoKey } from "./auth";

interface SearchResult {
  id: string;
  group: string;
  label: string;
  detail: string;
  path: string;
}

interface AppNotification {
  id: string;
  title: string;
  detail: string;
  time: string;
  path: string;
  read: boolean;
}

function buildSearchResults(
  incident: RecallIncident,
  tasks: StaffTask[],
  query: string,
): SearchResult[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const matches = (...values: string[]) =>
    values.some((value) => value.toLowerCase().includes(q));
  const results: SearchResult[] = [];

  if (matches(incident.product, incident.title, incident.lotRange)) {
    results.push({
      id: incident.id,
      group: "Recall",
      label: incident.product,
      detail: `${incident.title} · Lots ${incident.lotRange}`,
      path: "/",
    });
  }
  incident.inventory.forEach((row) => {
    if (matches(row.store, row.sku, row.product, row.lot, row.location, row.status)) {
      results.push({
        id: row.id,
        group: "Inventory",
        label: `${row.product} · ${row.lot}`,
        detail: `${row.store} · ${row.location} · ${row.status}`,
        path: "/inventory",
      });
    }
  });
  tasks.forEach((task) => {
    if (matches(task.title, task.store, task.assignee, task.priority)) {
      results.push({
        id: task.id,
        group: "Task",
        label: task.title,
        detail: `${task.store} · ${task.assignee} · due ${task.due}`,
        path: "/tasks",
      });
    }
  });
  incident.evidence.forEach((item) => {
    if (matches(item.label, item.status)) {
      results.push({
        id: item.id,
        group: "Evidence",
        label: item.label,
        detail: item.status.replace("-", " "),
        path: "/evidence",
      });
    }
  });
  incident.agents.forEach((agent) => {
    if (matches(agent.name, agent.action)) {
      results.push({
        id: agent.id,
        group: "Agent",
        label: agent.name,
        detail: agent.action,
        path: "/agents",
      });
    }
  });
  return results.slice(0, 9);
}

function buildNotifications(incident: RecallIncident): AppNotification[] {
  const fromMilestones = incident.milestones.slice(0, 2).map((milestone) => ({
    id: `milestone-${milestone.id}`,
    title: milestone.title,
    detail: milestone.due,
    time: `${milestone.remaining} left`,
    path: "/tasks",
    read: false,
  }));
  const fromWorkflow = incident.workflow
    .filter((step) => step.status === "complete")
    .slice(-2)
    .map((step) => ({
      id: `workflow-${step.id}`,
      title: step.title,
      detail: step.detail,
      time: step.time,
      path: "/timeline",
      read: false,
    }));
  const fromInsights = incident.insights.slice(0, 1).map((insight) => ({
    id: `insight-${insight.id}`,
    title: insight.title,
    detail: insight.detail,
    time: incident.openedAt,
    path: "/memory",
    read: false,
  }));
  return [...fromMilestones, ...fromWorkflow, ...fromInsights];
}

export function TopBar({
  incident,
  tasks,
  provider,
  providerProof,
  providerEvidenceState,
  searchQuery,
  onSearchChange,
  searchRef,
}: {
  incident: RecallIncident;
  tasks: StaffTask[];
  provider: ProviderStatus | null;
  providerProof: QwenVerificationReceipt | null;
  providerEvidenceState: ProviderProofState;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  searchRef: React.RefObject<HTMLInputElement>;
}) {
  const navigate = useNavigate();
  const [searchOpen, setSearchOpen] = useState(false);
  const [notifications, setNotifications] = useState<AppNotification[]>(() =>
    buildNotifications(incident),
  );
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  const results = useMemo(
    () => buildSearchResults(incident, tasks, searchQuery),
    [incident, tasks, searchQuery],
  );
  const showResults = searchOpen && searchQuery.trim().length > 0;
  const unreadCount = notifications.filter((item) => !item.read).length;

  const closeSearch = () => setSearchOpen(false);
  const selectResult = (result: SearchResult) => {
    navigate(result.path);
    onSearchChange("");
    setSearchOpen(false);
  };
  const openNotification = (notification: AppNotification) => {
    setNotifications((current) =>
      current.map((item) => (item.id === notification.id ? { ...item, read: true } : item)),
    );
    setNotificationsOpen(false);
    navigate(notification.path);
  };
  const markAllRead = () =>
    setNotifications((current) => current.map((item) => ({ ...item, read: true })));
  const signOut = () => {
    clearDemoKey();
    setProfileOpen(false);
    navigate("/");
  };

  return (
    <header className="topbar">
      <div
        className="search-box"
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            closeSearch();
            searchRef.current?.blur();
          }
        }}
      >
        <Search size={18} aria-hidden="true" />
        <input
          type="search"
          aria-label="Search recalls, lots, stores, tasks, evidence"
          placeholder="Search recalls, lots, stores, tasks, evidence..."
          ref={searchRef}
          value={searchQuery}
          role="combobox"
          aria-expanded={showResults}
          aria-controls="global-search-results"
          onChange={(event) => {
            onSearchChange(event.currentTarget.value);
            setSearchOpen(true);
          }}
          onFocus={() => setSearchOpen(true)}
        />
        <kbd>⌘K</kbd>
        {showResults ? (
          <>
            <button
              type="button"
              className="dropdown-backdrop"
              aria-label="Close search results"
              tabIndex={-1}
              onClick={closeSearch}
            />
            <div className="search-results" id="global-search-results" role="listbox">
              {results.length === 0 ? (
                <p className="dropdown-note">
                  No matches for <strong>{searchQuery.trim()}</strong>. Try a lot code,
                  store, task, or agent name.
                </p>
              ) : (
                results.map((result) => (
                  <button
                    key={`${result.group}-${result.id}`}
                    type="button"
                    role="option"
                    aria-selected="false"
                    className="search-result"
                    onClick={() => selectResult(result)}
                  >
                    <span className="search-result-top">
                      <strong>{result.label}</strong>
                      <span className="search-result-group">{result.group}</span>
                    </span>
                    <small>{result.detail}</small>
                  </button>
                ))
              )}
            </div>
          </>
        ) : null}
      </div>

      <div className="topbar-actions">
        <ProviderEvidenceControl
          provider={provider}
          proof={providerProof}
          state={providerEvidenceState}
        />
        <div className="incident-status">
          <span>Incident Status</span>
          <strong>{incident.status.toUpperCase()}</strong>
        </div>
        <div
          className="dropdown"
          onKeyDown={(event) => {
            if (event.key === "Escape") setNotificationsOpen(false);
          }}
        >
          <button
            type="button"
            className="icon-button"
            aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
            aria-haspopup="menu"
            aria-expanded={notificationsOpen}
            onClick={() => setNotificationsOpen((open) => !open)}
          >
            <Bell size={20} />
            {unreadCount > 0 && <span className="notification-badge">{unreadCount}</span>}
          </button>
          {notificationsOpen ? (
            <>
              <button
                type="button"
                className="dropdown-backdrop"
                aria-label="Close notifications"
                tabIndex={-1}
                onClick={() => setNotificationsOpen(false)}
              />
              <div className="dropdown-menu notifications-menu" role="menu">
                <div className="menu-header">
                  <strong>Notifications</strong>
                  <button
                    type="button"
                    className="link-button"
                    onClick={markAllRead}
                    disabled={unreadCount === 0}
                  >
                    <CheckCheck size={14} />
                    Mark all as read
                  </button>
                </div>
                {notifications.map((notification) => (
                  <button
                    key={notification.id}
                    type="button"
                    role="menuitem"
                    className={`notification-row ${notification.read ? "" : "unread"}`}
                    onClick={() => openNotification(notification)}
                  >
                    <span className="notification-title">
                      <span className="notification-dot" aria-hidden="true" />
                      {notification.title}
                    </span>
                    <p>{notification.detail}</p>
                    <time>{notification.time}</time>
                  </button>
                ))}
              </div>
            </>
          ) : null}
        </div>
        <div
          className="dropdown"
          onKeyDown={(event) => {
            if (event.key === "Escape") setProfileOpen(false);
          }}
        >
          <button
            type="button"
            className="profile-button"
            aria-haspopup="menu"
            aria-expanded={profileOpen}
            onClick={() => setProfileOpen((open) => !open)}
          >
            <span className="avatar">OM</span>
            <span className="profile-copy">
              <strong>Operations Manager</strong>
              <span>Central Foods Co.</span>
            </span>
            <ChevronDown size={16} />
          </button>
          {profileOpen ? (
            <>
              <button
                type="button"
                className="dropdown-backdrop"
                aria-label="Close profile menu"
                tabIndex={-1}
                onClick={() => setProfileOpen(false)}
              />
              <div className="dropdown-menu" role="menu">
                <p className="dropdown-note">
                  Signed in as <strong>Operations Manager</strong>
                  <br />
                  Central Foods Co. · demo workspace
                </p>
                <Link
                  to="/settings"
                  role="menuitem"
                  className="dropdown-item"
                  onClick={() => setProfileOpen(false)}
                >
                  <Settings size={15} />
                  Profile & settings
                </Link>
                <button type="button" role="menuitem" className="dropdown-item" disabled>
                  <UserRound size={15} />
                  Switch account (demo)
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="dropdown-item"
                  onClick={signOut}
                >
                  <LogOut size={15} />
                  Sign out
                </button>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </header>
  );
}
