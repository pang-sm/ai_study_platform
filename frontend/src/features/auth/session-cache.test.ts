import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import { evictUserPrivateQueries } from './session-cache';
import { authKeys } from './query-keys';

function seededClient() {
  const client = new QueryClient();
  client.setQueryData(['exam', 'catalog'], { catalog_version: 'v2' });
  client.setQueryData(['exam', 'subject-content-status', 'cs_408'], { availability: 'active' });
  client.setQueryData(['exam', 'scientific-capabilities'], { components: [] });
  client.setQueryData(authKeys.session, { username: 'learner_a' });
  client.setQueryData(['learning', 'agenda'], { items: [{ title: '私有计划' }] });
  client.setQueryData(['profile', 'detail'], { profile: { username: 'learner_a' } });
  client.setQueryData(['profile', 'usage'], { tier: 'free', periods: {} });
  client.setQueryData(['review', 'summary'], { total: 3 });
  client.setQueryData(['learning-records', 'recent', 'all', 8], [{ event_id: 'x' }]);
  client.setQueryData(['programming', 'records'], { rows: [] });
  return client;
}

describe('evictUserPrivateQueries', () => {
  it('drops every user-private entry so the next visitor cannot read them', () => {
    const client = seededClient();
    evictUserPrivateQueries(client);

    expect(client.getQueryData(['learning', 'agenda'])).toBeUndefined();
    expect(client.getQueryData(['profile', 'detail'])).toBeUndefined();
    expect(client.getQueryData(['profile', 'usage'])).toBeUndefined();
    expect(client.getQueryData(['review', 'summary'])).toBeUndefined();
    expect(client.getQueryData(['learning-records', 'recent', 'all', 8])).toBeUndefined();
    expect(client.getQueryData(['programming', 'records'])).toBeUndefined();
  });

  it('leaves public catalog reads in place', () => {
    const client = seededClient();
    evictUserPrivateQueries(client);

    expect(client.getQueryData(['exam', 'catalog'])).toEqual({ catalog_version: 'v2' });
    expect(client.getQueryData(['exam', 'subject-content-status', 'cs_408'])).toEqual({
      availability: 'active',
    });
    expect(client.getQueryData(['exam', 'scientific-capabilities'])).toEqual({ components: [] });
  });

  it('leaves the session entry alone, because login and logout write it explicitly', () => {
    const client = seededClient();
    evictUserPrivateQueries(client);

    expect(client.getQueryData(authKeys.session)).toEqual({ username: 'learner_a' });
  });
});
