import { Outlet, createFileRoute } from '@tanstack/react-router';
export const Route = createFileRoute('/programming/$language')({ component: Outlet });
