/*
 * Adapted from modelcontextprotocol/typescript-sdk v1.29.0 src/client/auth.ts.
 * Copyright (c) 2024 Anthropic, PBC. Licensed under MIT; see LICENSES/.
 * Modified to remove Zod/CORS shims and enforce authorization-server issuer validation.
 */

import type { McpFetch } from "../auth-provider.ts";
import { LATEST_PROTOCOL_VERSION } from "../protocol/types.ts";
import { OAuthIssuerMismatchError } from "./errors.ts";
import {
	type AuthorizationServerMetadata,
	type OAuthChallenge,
	type OAuthProtectedResourceMetadata,
	type OAuthServerInfo,
	parseAuthorizationServerMetadata,
	parseProtectedResourceMetadata,
} from "./types.ts";

const MAX_DISCOVERY_REDIRECTS = 3;
const REDIRECT_STATUSES = new Set([301, 302, 303, 307, 308]);

export interface OAuthDiscoveryOptions {
	readonly trustedDiscoveryOrigins?: readonly string[];
}

class OAuthDiscoverySecurityError extends Error {}

function discard(response: Response | undefined): void {
	void response?.body?.cancel().catch(() => {});
}

/** 4xx and 502 mean "not here", so discovery tries the next candidate URL. */
function isDiscoveryMiss(status: number): boolean {
	return (status >= 400 && status < 500) || status === 502;
}

/** Path suffix for `/.well-known/<kind><path>`; empty for the root path. */
function pathSuffix(pathname: string): string {
	return pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
}

function field(header: string, name: string): string | undefined {
	const match = header.match(new RegExp(String.raw`(?:^|[,\s])${name}=(?:"([^"]*)"|([^\s,]+))`, "i"));
	return match?.[1] ?? match?.[2];
}

export function parseWwwAuthenticate(header: string | null): OAuthChallenge {
	if (!header) return {};
	const scheme = header.trimStart().split(/\s+/, 1)[0]?.toLowerCase();
	if (scheme !== "bearer" && scheme !== "dpop") return {};
	const resourceMetadata = field(header, "resource_metadata");
	let resourceMetadataUrl: URL | undefined;
	if (resourceMetadata) {
		try {
			resourceMetadataUrl = new URL(resourceMetadata);
		} catch {}
	}
	return {
		resourceMetadataUrl,
		scope: field(header, "scope"),
		error: field(header, "error"),
		errorDescription: field(header, "error_description"),
	};
}

function trustedOrigins(serverUrl: string | URL, configured: readonly string[] = []): ReadonlySet<string> {
	const values = [new URL(serverUrl).origin, ...configured];
	return new Set(
		values.map((value) => {
			const url = new URL(value);
			if (url.username || url.password) {
				throw new OAuthDiscoverySecurityError("OAuth discovery origin must not contain credentials");
			}
			return url.origin;
		}),
	);
}

function validateDiscoveryUrl(value: string | URL, origins: ReadonlySet<string>): URL {
	const url = new URL(value);
	if (url.username || url.password) {
		throw new OAuthDiscoverySecurityError("OAuth discovery URL must not contain credentials");
	}
	if (!origins.has(url.origin)) {
		throw new OAuthDiscoverySecurityError(`OAuth discovery origin is not trusted: ${url.origin}`);
	}
	return url;
}

function validateMetadataEndpoints(metadata: AuthorizationServerMetadata, origins: ReadonlySet<string>): void {
	validateDiscoveryUrl(metadata.issuer, origins);
	validateDiscoveryUrl(metadata.authorization_endpoint, origins);
	validateDiscoveryUrl(metadata.token_endpoint, origins);
	if (metadata.registration_endpoint !== undefined) validateDiscoveryUrl(metadata.registration_endpoint, origins);
}

/** Revalidate cached OAuth discovery data against the current server trust boundary. */
export function validateOAuthServerInfo(
	serverUrl: string | URL,
	info: OAuthServerInfo,
	configured: readonly string[] = [],
): void {
	const origins = trustedOrigins(serverUrl, configured);
	validateDiscoveryUrl(info.authorizationServerUrl, origins);
	if (info.authorizationServerMetadata !== undefined) {
		validateMetadataEndpoints(info.authorizationServerMetadata, origins);
	}
	if (info.resourceMetadata?.authorization_servers !== undefined) {
		for (const value of info.resourceMetadata.authorization_servers) validateDiscoveryUrl(value, origins);
	}
}

async function fetchMetadata(
	initialUrl: URL,
	fetch: McpFetch,
	protocolVersion: string,
	origins: ReadonlySet<string>,
): Promise<Response> {
	let url = validateDiscoveryUrl(initialUrl, origins);
	for (let redirects = 0; ; redirects += 1) {
		const response = await fetch(url, {
			redirect: "manual",
			headers: { Accept: "application/json", "MCP-Protocol-Version": protocolVersion },
		});
		if (!REDIRECT_STATUSES.has(response.status)) return response;
		if (redirects >= MAX_DISCOVERY_REDIRECTS) {
			discard(response);
			throw new OAuthDiscoverySecurityError("OAuth discovery exceeded its redirect bound");
		}
		const location = response.headers.get("location");
		if (location === null) return response;
		discard(response);
		url = validateDiscoveryUrl(new URL(location, url), origins);
	}
}

export async function discoverProtectedResourceMetadata(
	serverUrl: string | URL,
	options: OAuthDiscoveryOptions & {
		resourceMetadataUrl?: string | URL;
		protocolVersion?: string;
		fetch?: McpFetch;
	} = {},
): Promise<OAuthProtectedResourceMetadata> {
	const server = new URL(serverUrl);
	const fetch = options.fetch ?? globalThis.fetch;
	const version = options.protocolVersion ?? LATEST_PROTOCOL_VERSION;
	const origins = trustedOrigins(server, options.trustedDiscoveryOrigins);
	let response = await fetchMetadata(
		options.resourceMetadataUrl
			? new URL(options.resourceMetadataUrl)
			: new URL(`/.well-known/oauth-protected-resource${pathSuffix(server.pathname)}`, server.origin),
		fetch,
		version,
		origins,
	);
	if (!options.resourceMetadataUrl && server.pathname !== "/" && isDiscoveryMiss(response.status)) {
		discard(response);
		response = await fetchMetadata(
			new URL("/.well-known/oauth-protected-resource", server.origin),
			fetch,
			version,
			origins,
		);
	}
	if (!response.ok) {
		discard(response);
		throw new Error(`HTTP ${response.status} loading OAuth protected resource metadata`);
	}
	return parseProtectedResourceMetadata(await response.json());
}

export function buildAuthorizationServerDiscoveryUrls(
	authorizationServerUrl: string | URL,
): { url: URL; type: "oauth" | "oidc" }[] {
	const issuer = new URL(authorizationServerUrl);
	const path = pathSuffix(issuer.pathname);
	const urls: { url: URL; type: "oauth" | "oidc" }[] = [
		{ url: new URL(`/.well-known/oauth-authorization-server${path}`, issuer.origin), type: "oauth" },
		{ url: new URL(`/.well-known/openid-configuration${path}`, issuer.origin), type: "oidc" },
	];
	if (path) urls.push({ url: new URL(`${path}/.well-known/openid-configuration`, issuer.origin), type: "oidc" });
	return urls;
}

export async function discoverAuthorizationServerMetadata(
	authorizationServerUrl: string | URL,
	options: OAuthDiscoveryOptions & {
		fetch?: McpFetch;
		protocolVersion?: string;
		skipIssuerValidation?: boolean;
	} = {},
): Promise<AuthorizationServerMetadata | undefined> {
	const fetch = options.fetch ?? globalThis.fetch;
	const origins = trustedOrigins(authorizationServerUrl, options.trustedDiscoveryOrigins);
	for (const { url } of buildAuthorizationServerDiscoveryUrls(authorizationServerUrl)) {
		const response = await fetchMetadata(url, fetch, options.protocolVersion ?? LATEST_PROTOCOL_VERSION, origins);
		if (!response.ok) {
			discard(response);
			if (isDiscoveryMiss(response.status)) continue;
			throw new Error(`HTTP ${response.status} loading authorization server metadata from ${url}`);
		}
		const metadata = parseAuthorizationServerMetadata(await response.json());
		if (!options.skipIssuerValidation) {
			const expected = String(authorizationServerUrl);
			// URL parsing adds a trailing slash to bare origins, so compare without one on either side.
			const trim = (value: string) => (value.endsWith("/") ? value.slice(0, -1) : value);
			if (trim(metadata.issuer) !== trim(expected)) throw new OAuthIssuerMismatchError(expected, metadata.issuer);
		}
		validateMetadataEndpoints(metadata, origins);
		return metadata;
	}
	return undefined;
}

export async function discoverOAuthServerInfo(
	serverUrl: string | URL,
	options: {
		resourceMetadataUrl?: URL;
		fetch?: McpFetch;
		skipIssuerValidation?: boolean;
		trustedDiscoveryOrigins?: readonly string[];
	} = {},
): Promise<OAuthServerInfo> {
	const origins = trustedOrigins(serverUrl, options.trustedDiscoveryOrigins);
	let resourceMetadata: OAuthProtectedResourceMetadata | undefined;
	try {
		resourceMetadata = await discoverProtectedResourceMetadata(serverUrl, {
			resourceMetadataUrl: options.resourceMetadataUrl,
			fetch: options.fetch,
			trustedDiscoveryOrigins: [...origins],
		});
	} catch (error) {
		if (error instanceof TypeError || error instanceof OAuthDiscoverySecurityError) throw error;
	}
	const authorizationServerUrl = resourceMetadata?.authorization_servers?.[0] ?? String(new URL("/", serverUrl));
	validateDiscoveryUrl(authorizationServerUrl, origins);
	const info: OAuthServerInfo = {
		authorizationServerUrl,
		authorizationServerMetadata: await discoverAuthorizationServerMetadata(authorizationServerUrl, {
			fetch: options.fetch,
			skipIssuerValidation: options.skipIssuerValidation,
			trustedDiscoveryOrigins: [...origins],
		}),
		resourceMetadata,
	};
	validateOAuthServerInfo(serverUrl, info, options.trustedDiscoveryOrigins);
	return info;
}

export function resourceUrlFromServerUrl(value: string | URL): URL {
	const url = new URL(value);
	url.hash = "";
	return url;
}

export function selectResource(serverUrl: string | URL, metadata?: OAuthProtectedResourceMetadata): string | undefined {
	if (!metadata) return undefined;
	const requested = resourceUrlFromServerUrl(serverUrl);
	const configured = new URL(metadata.resource);
	if (requested.origin !== configured.origin) {
		throw new Error(`Protected resource ${metadata.resource} does not match MCP server ${requested}`);
	}
	const requestedPath = requested.pathname.endsWith("/") ? requested.pathname : `${requested.pathname}/`;
	const configuredPath = configured.pathname.endsWith("/") ? configured.pathname : `${configured.pathname}/`;
	if (!requestedPath.startsWith(configuredPath)) {
		throw new Error(`Protected resource ${metadata.resource} does not match MCP server ${requested}`);
	}
	return metadata.resource;
}
