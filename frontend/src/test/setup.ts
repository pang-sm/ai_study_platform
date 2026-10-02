import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// Vitest does not expose globals here, so register RTL cleanup explicitly.
afterEach(cleanup);

Object.defineProperty(window, 'scrollTo', { value: () => undefined, writable: true });

// CodeMirror cannot lay text out in jsdom (`Range.getClientRects` is missing), so the workbench's
// editor is replaced everywhere by a textarea with the same label. See `./code-editor-stub.tsx`.
vi.mock('@/features/programming/components/workbench/code-editor', () => import('./code-editor-stub'));
