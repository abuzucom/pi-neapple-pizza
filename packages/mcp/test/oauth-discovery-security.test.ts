import { describe, expect, it } from "vitest";
import {
	discoverAuthorizationServerMetadata,
	discoverOAuthServerInfo,
	discoverProtectedResourceMetadata,
	validateOAuthServerInfo,
} from "../src/oauth/discovery.ts";

const server = "https://mcp.example.test/rpc";

describe("OAuth discovery boundaries", () => {
	it("rejects cross-origin protected-resource metadata by default", async () => {
		let called = false;
		await expect(
			discoverProtectedResourceMetadata(server, {
				resourceMetadataUrl: "https://attacker.test/metadata",
				fetch: async () => {
					called = true;
					return new Response();
				},
			}),
		).rejects.toThrow("origin is not trusted");
		expect(called).toBe(false);
	});

	it("permits one exact configured discovery origin", async () => {
		const metadata = await discoverProtectedResourceMetadata(server, {
			resourceMetadataUrl: "https://identity.example.test/metadata",
			trustedDiscoveryOrigins: ["https://identity.example.test"],
			fetch: async () =>
				new Response(JSON.stringify({ resource: server }), {
					status: 200,
					headers: { "content-type": "application/json" },
				}),
		});
		expect(metadata.resource).toBe(server);
	});

	it("rejects credentials in discovery URLs", async () => {
		await expect(
			discoverProtectedResourceMetadata(server, {
				resourceMetadataUrl: "https://user:secret@mcp.example.test/metadata",
			}),
		).rejects.toThrow("must not contain credentials");
	});

	it("rejects a cross-origin discovery redirect", async () => {
		await expect(
			discoverProtectedResourceMetadata(server, {
				fetch: async () =>
					new Response(null, { status: 302, headers: { location: "https://attacker.test/metadata" } }),
			}),
		).rejects.toThrow("origin is not trusted");
	});

	it.each(["http://127.0.0.1/metadata", "http://169.254.169.254/metadata"])(
		"rejects an untrusted local discovery target %s through the complete flow",
		async (resourceMetadataUrl) => {
			let called = false;
			await expect(
				discoverOAuthServerInfo(server, {
					resourceMetadataUrl: new URL(resourceMetadataUrl),
					fetch: async () => {
						called = true;
						return new Response();
					},
				}),
			).rejects.toThrow("origin is not trusted");
			expect(called).toBe(false);
		},
	);

	it("rejects redirect loops through the complete flow", async () => {
		let calls = 0;
		await expect(
			discoverOAuthServerInfo(server, {
				fetch: async () => {
					calls += 1;
					return new Response(null, { status: 302, headers: { location: "/again" } });
				},
			}),
		).rejects.toThrow("redirect bound");
		expect(calls).toBe(4);
	});

	it("rejects cached cross-origin endpoints", () => {
		expect(() =>
			validateOAuthServerInfo(server, {
				authorizationServerUrl: "https://mcp.example.test",
				authorizationServerMetadata: {
					issuer: "https://mcp.example.test",
					authorization_endpoint: "https://attacker.test/authorize",
					token_endpoint: "https://mcp.example.test/token",
					response_types_supported: ["code"],
				},
			}),
		).toThrow("origin is not trusted");
	});

	it("rejects cross-origin authorization endpoints in metadata", async () => {
		await expect(
			discoverAuthorizationServerMetadata("https://identity.example.test", {
				fetch: async () =>
					new Response(
						JSON.stringify({
							issuer: "https://identity.example.test",
							authorization_endpoint: "https://attacker.test/authorize",
							token_endpoint: "https://identity.example.test/token",
							response_types_supported: ["code"],
						}),
						{ status: 200, headers: { "content-type": "application/json" } },
					),
			}),
		).rejects.toThrow("origin is not trusted");
	});
});
