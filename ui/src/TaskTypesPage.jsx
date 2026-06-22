import { useQuery } from '@apollo/client/react';
import dayjs from 'dayjs';
import _ from 'lodash';
import { useSearchParams } from 'react-router-dom';

import HumanTime from '@/components/HumanTime';
import StateBadge from '@/components/StateBadge';
import TaskLink from '@/components/TaskLink';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

import { GET_TASK_TYPES } from './queries';

const DAYS_OPTIONS = [
    { value: '1', label: 'Last 24 hours' },
    { value: '3', label: 'Last 3 days' },
    { value: '7', label: 'Last 7 days' },
    { value: '30', label: 'Last 30 days' },
];

function PageHeader({ days, onDaysChange }) {
    return (
        <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="flex flex-col gap-1">
                <h1 className="text-2xl font-semibold tracking-tight">Task Types</h1>
                <p className="text-sm text-muted-foreground">
                    Every registered task and the status of its most recent run.
                </p>
            </div>
            <Select value={String(days)} onValueChange={onDaysChange}>
                <SelectTrigger className="w-[160px]">
                    <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    {DAYS_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                            {option.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    );
}

function TaskTypeCard({ taskType }) {
    const latestRun = taskType.latestTaskRun;
    return (
        <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-card p-4 transition-colors hover:border-muted-foreground/30 hover:bg-accent/40">
            <div className="flex min-w-0 flex-col gap-0.5">
                <div className="font-medium">
                    <TaskLink taskType={taskType} />
                </div>
                <span className="truncate font-mono text-xs text-muted-foreground">{taskType.funcAddress}</span>
            </div>
            {latestRun ? (
                <div className="flex shrink-0 items-center gap-4">
                    <TaskLink taskRun={latestRun} />
                    <StateBadge state={latestRun.state} since={latestRun.stateSince} />
                    <span className="w-28 text-right text-xs text-muted-foreground">
                        <HumanTime timestamp={latestRun.createdAt} />
                    </span>
                </div>
            ) : (
                <span className="shrink-0 rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">Never run</span>
            )}
        </div>
    );
}

function SkeletonCard() {
    return (
        <div className="flex items-center justify-between gap-4 rounded-lg border border-border bg-card p-4">
            <div className="flex flex-col gap-2">
                <div className="h-4 w-40 animate-pulse rounded bg-muted" />
                <div className="h-3 w-56 animate-pulse rounded bg-muted" />
            </div>
            <div className="h-5 w-20 animate-pulse rounded bg-muted" />
        </div>
    );
}

function EmptyState({ days }) {
    return (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border bg-card/50 px-6 py-16 text-center">
            <p className="text-sm font-medium">No task runs in the last {days} days</p>
            <p className="max-w-md text-sm text-muted-foreground">
                Trigger a task from your application — or widen the time range above — and runs will appear here in real
                time.
            </p>
        </div>
    );
}

function ErrorState({ message }) {
    return (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            Failed to load task types: {message}
        </div>
    );
}

function TaskTypesPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const days = searchParams.get('days') || '3';
    const getTaskTypesQuery = useQuery(GET_TASK_TYPES, { variables: { days: parseInt(days) } });

    const setDays = (value) => {
        setSearchParams((prev) => {
            prev.set('days', value);
            return prev;
        });
    };

    let body;
    if (getTaskTypesQuery.loading) {
        body = (
            <div className="flex flex-col gap-3">
                {_.range(4).map((i) => (
                    <SkeletonCard key={i} />
                ))}
            </div>
        );
    } else if (getTaskTypesQuery.error) {
        body = <ErrorState message={getTaskTypesQuery.error.message} />;
    } else {
        const taskTypes = _.orderBy(
            getTaskTypesQuery.data.getTaskTypes,
            [(taskType) => (taskType.latestTaskRun ? dayjs(taskType.latestTaskRun.createdAt).unix() : -Infinity)],
            ['desc']
        );
        body =
            taskTypes.length === 0 ? (
                <EmptyState days={days} />
            ) : (
                <div className="flex flex-col gap-3">
                    {taskTypes.map((taskType) => (
                        <TaskTypeCard key={taskType.id} taskType={taskType} />
                    ))}
                </div>
            );
    }

    return (
        <div className="flex flex-col gap-6">
            <PageHeader days={days} onDaysChange={setDays} />
            {body}
        </div>
    );
}

export default TaskTypesPage;
