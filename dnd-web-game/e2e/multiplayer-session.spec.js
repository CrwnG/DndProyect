/**
 * E2E: multiplayer session identity (the D2 batch) over the real HTTP/WS stack.
 *
 * There is no lobby entry point in the UI yet (follow-up), so these exercise the
 * REST session flow via Playwright's request API and the token-gated websocket
 * from inside a real browser context.
 */

const { test, expect } = require('@playwright/test');

test.describe('Multiplayer session identity', () => {
    test('create -> join -> duplicate join is rejected', async ({ request }) => {
        const created = await request.post('/api/multiplayer/session', {
            data: { host_id: 'e2e-host', host_name: 'Ana' },
        });
        expect(created.ok()).toBeTruthy();
        const session = await created.json();
        expect(session.code).toHaveLength(6);
        expect(session.token).toBeTruthy();

        const joined = await request.post(`/api/multiplayer/session/${session.code}/join`, {
            data: { player_id: 'e2e-p2', player_name: 'Bo' },
        });
        expect(joined.ok()).toBeTruthy();

        const dup = await request.post(`/api/multiplayer/session/${session.code}/join`, {
            data: { player_id: 'e2e-p2', player_name: 'Evil Bo' },
        });
        expect(dup.status()).toBe(409);
    });

    test('the websocket refuses a missing token and accepts a valid one', async ({ page, request }) => {
        const created = await (await request.post('/api/multiplayer/session', {
            data: { host_id: 'e2e-ws-host', host_name: 'Ana' },
        })).json();

        await page.goto('/');
        const probe = (code, playerId, token) => page.evaluate(([c, p, t]) => {
            return new Promise((resolve) => {
                const q = t ? `?token=${encodeURIComponent(t)}` : '';
                const ws = new WebSocket(`ws://localhost:8000/api/multiplayer/ws/${c}/${p}${q}`);
                const timer = setTimeout(() => { ws.close(); resolve('open'); }, 2500);
                ws.onclose = (e) => { clearTimeout(timer); resolve(e.code); };
            });
        }, [code, playerId, token]);

        expect(await probe(created.code, 'e2e-ws-host', null)).toBe(4401);
        expect(await probe(created.code, 'e2e-ws-host', 'wrong')).toBe(4401);
        expect(await probe(created.code, 'e2e-ws-host', created.token)).toBe('open');
    });
});
