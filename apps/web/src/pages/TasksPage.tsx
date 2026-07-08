import { useState, useMemo } from "react";
import {
  Check,
  UserRound,
  ChevronDown,
  CheckCircle2,
} from "lucide-react";
import type { StaffTask, Severity, TaskStatus } from "../types";
import { PanelHeader, SeverityPill, TaskState, formatTaskStatus } from "./shared";

interface TasksPageProps {
  tasks: StaffTask[];
  onToggleTask: (taskId: string) => void;
  onAssignToMe: () => void;
}

const severityRank: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

const taskStatusRank: Record<TaskStatus, number> = {
  blocked: 0,
  "in-progress": 1,
  "not-started": 2,
  complete: 3,
};

type TaskSort = "priority" | "due" | "status";

const taskSortLabels: Record<TaskSort, string> = {
  priority: "Priority",
  due: "Due",
  status: "Status",
};

export function TasksPage({ tasks, onToggleTask, onAssignToMe }: TasksPageProps) {
  const [sort, setSort] = useState<TaskSort>("priority");
  const openCount = tasks.filter((task) => task.status !== "complete").length;

  const sortedTasks = useMemo(() => {
    const copy = [...tasks];
    if (sort === "priority") {
      copy.sort((a, b) => severityRank[a.priority] - severityRank[b.priority]);
    } else if (sort === "status") {
      copy.sort((a, b) => taskStatusRank[a.status] - taskStatusRank[b.status]);
    } else {
      copy.sort((a, b) => a.due.localeCompare(b.due));
    }
    return copy;
  }, [tasks, sort]);

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Staff Task Board</h1>
        <div className="page-header-actions">
          <span className="count-badge">{openCount} Open</span>
          <button
            type="button"
            className="utility-button"
            onClick={onAssignToMe}
            disabled={openCount === 0}
          >
            <UserRound size={16} />
            Assign to me
          </button>
        </div>
      </div>

      <section className="panel task-panel full-width" aria-labelledby="tasks-title">
        <div className="panel-header with-actions">
          <h2 id="tasks-title">Tasks</h2>
          <div className="table-actions">
            <div className="dropdown">
              <button type="button" className="utility-button">
                Sort: {taskSortLabels[sort]}
                <ChevronDown size={15} />
              </button>
              <div className="dropdown-menu">
                {(Object.keys(taskSortLabels) as TaskSort[]).map((option) => (
                  <button
                    key={option}
                    type="button"
                    className={`dropdown-item ${sort === option ? "selected" : ""}`}
                    onClick={() => setSort(option)}
                  >
                    {sort === option ? <Check size={15} /> : null}
                    {taskSortLabels[option]}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="table-wrap compact">
          <table>
            <thead>
              <tr>
                <th scope="col">Task</th>
                <th scope="col">Store</th>
                <th scope="col">Priority</th>
                <th scope="col">Assignee</th>
                <th scope="col">Due</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {sortedTasks.map((task) => (
                <tr key={task.id} className={task.status === "complete" ? "done" : ""}>
                  <td>
                    <label className="task-check">
                      <input
                        type="checkbox"
                        checked={task.status === "complete"}
                        onChange={() => onToggleTask(task.id)}
                      />
                      <span>{task.title}</span>
                    </label>
                  </td>
                  <td>{task.store}</td>
                  <td>
                    <SeverityPill severity={task.priority} />
                  </td>
                  <td>
                    <span className="assignee">
                      <span>{task.initials}</span>
                      {task.assignee}
                    </span>
                  </td>
                  <td>{task.due}</td>
                  <td>
                    <TaskState status={task.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {tasks.length === 0 ? (
            <p className="empty-note">No staff tasks found.</p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
