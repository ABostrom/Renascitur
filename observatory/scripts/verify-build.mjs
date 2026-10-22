// Fails if the committed build is stale: rebuild, then ask git whether build/ changed.
//   npm run verify-build
import { execSync } from 'node:child_process';

execSync('npx vite build', { stdio: 'inherit' });
try {
	execSync('git diff --quiet --exit-code -- build', { stdio: 'inherit' });
	execSync('git ls-files --others --exclude-standard --error-unmatch build', { stdio: 'ignore' });
	console.error('verify-build: build/ has new files; commit them');
	process.exit(1);
} catch (e) {
	if (e.status === 1 && e.cmd?.startsWith('git diff')) {
		console.error('verify-build: the committed build is stale; commit the rebuilt build/');
		process.exit(1);
	}
}
console.log('verify-build: the committed build matches the source');
