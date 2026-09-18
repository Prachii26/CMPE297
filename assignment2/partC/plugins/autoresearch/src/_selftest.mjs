import { staticGuard, checkTiming, checkMetricPlausibility } from './guard.js'
import { runTrainPy, runEvaluatePy } from './runner.js'

console.log('--- guard.js unit checks ---')
console.log('clean code:', staticGuard('model = DecisionTreeClassifier(max_depth=5)\nmodel.fit(X_train, y_train)'))
console.log('forbidden ref:', staticGuard('from harness.data import load_heldout\nX, y = load_heldout()'))
console.log('comment mentioning heldout (should now PASS):', staticGuard('# Note: never touch heldout data\nmodel.fit(X_train, y_train)'))
console.log('docstring mentioning heldout (should now PASS):', staticGuard('"""\nContract: no held-out data ever reaches this file.\n"""\nmodel.fit(X_train, y_train)'))
console.log('evaluate.py mention in real code:', staticGuard('import harness.evaluate'))
console.log('suspicious write:', staticGuard('open("harness/evaluate.py", "w").write("hacked")'))
console.log('hardcoded array:', staticGuard('preds = [' + Array(60).fill('1').join(', ') + ']'))
console.log('timing ok:', checkTiming(1.5, 1.9))
console.log('timing too fast:', checkTiming(0.02, 1.9))
console.log('timing floor:', checkTiming(0.01, 1.9))
console.log('metric ok:', checkMetricPlausibility(0.85))
console.log('metric implausible:', checkMetricPlausibility(0.999))

console.log('\n--- runner.js against the real baseline ---')
const rootDir = process.argv[2]
const trainResult = await runTrainPy(rootDir)
console.log('train.py exitCode:', trainResult.exitCode, 'elapsed:', trainResult.elapsedSeconds.toFixed(3) + 's')
console.log('train.py stdout:\n' + trainResult.stdout)
if (trainResult.stderr) console.log('train.py stderr:\n' + trainResult.stderr)

const evalResult = await runEvaluatePy(rootDir)
console.log('evaluate.py exitCode:', evalResult.exitCode, 'accuracy:', evalResult.accuracy, 'nHeldout:', evalResult.nHeldout)
if (evalResult.stderr) console.log('evaluate.py stderr:\n' + evalResult.stderr)
