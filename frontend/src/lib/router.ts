/**
 * TanStack Router types every `to` as a literal union of the routes it generated. Some
 * navigation is composed at runtime — a breadcrumb trail, a context tab list, a server-supplied
 * destination — and those paths are built from the same route table the links point into. The
 * widening is confined to this one function so no component needs its own cast.
 */
export function routePath(path: string): '/' {
  return path as '/';
}
