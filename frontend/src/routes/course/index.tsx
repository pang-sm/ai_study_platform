import { createFileRoute } from '@tanstack/react-router';
import { CourseIndex } from '@/features/course/components/course-index';
export const Route = createFileRoute('/course/')({ component: CourseIndex });
