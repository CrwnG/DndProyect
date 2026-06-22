/**
 * Real contract tests for the API client — imports the ACTUAL module (not a
 * mock) and asserts each method maps to the right URL + request body. This is
 * exactly the class of test that would have caught the recurring drift bugs:
 * the doubled `/api` auth prefix and the dropped collectLoot party-split arg.
 */
import api from '../../js/api/api-client.js';

describe('APIClient request contracts', () => {
  beforeEach(() => {
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    );
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('GET builds the base /api URL', async () => {
    await api.get('/health');
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url] = global.fetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/health');
  });

  test('collectLoot forwards party_character_ids (regression guard)', async () => {
    await api.collectLoot('combat-1', 'char-1', [], true, ['p1', 'p2']);
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toContain('/loot/combat/combat-1/collect');
    const body = JSON.parse(opts.body);
    expect(body.character_id).toBe('char-1');
    expect(body.take_coins).toBe(true);
    expect(body.party_character_ids).toEqual(['p1', 'p2']);
  });

  test('useReaction nests reactor_id and forwards trigger context in extra_data', async () => {
    await api.useReaction('combat-1', 'reactor-1', 'shield', 'attacker-1', {
      incoming_damage: 12,
      attack_roll: 16,
    });
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toContain('/combat/reaction');
    const body = JSON.parse(opts.body);
    expect(body.reaction_type).toBe('shield');
    expect(body.trigger_source_id).toBe('attacker-1');
    expect(body.extra_data.reactor_id).toBe('reactor-1');
    expect(body.extra_data.incoming_damage).toBe(12);
    expect(body.extra_data.attack_roll).toBe(16);
  });

  test('a failed response rejects with an APIError carrying the status', async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({ detail: 'nope' }) })
    );
    await expect(api.get('/missing')).rejects.toMatchObject({ status: 404 });
  });
});
