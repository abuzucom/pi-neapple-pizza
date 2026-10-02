import { lchownSync, lstatSync, readdirSync } from "node:fs";
import { join } from "node:path";

/** Set ownership on each directory entry without following symbolic links. */
export function setTreeOwnership(targetPath: string, uid: number, gid: number): void {
	const pending = [targetPath];
	while (pending.length > 0) {
		const current = pending.pop();
		if (current === undefined) continue;
		const stats = lstatSync(current);
		if (stats.isDirectory() && !stats.isSymbolicLink()) {
			const entries = readdirSync(current);
			for (const entry of entries) pending.push(join(current, entry));
		}
		lchownSync(current, uid, gid);
	}
}
