// Builds the Python environments ABBA otherwise builds on first use, through Appose. Headless, no SciJava context.
//
//     args[0]: a comma-separated subset of deepslice,elastix,brainglobe ("none": only the jars are resolved)
//
// Prints ABBA_PREPARE lines for the user (ABBA_PREPARE_LOG: what Appose says while building), and ABBA_PHASE
// <environment> start / done for the progress bar; the rest of the output
// is the libraries' own. Exit code 1 if an environment did not build.
//
// ABBA 0.25.0 builds the DeepSlice environment in a package-private method; Groovy calls it all the same. From
// 0.25.1, ApposeDeepSliceTask.environment is public (and ABBA - Prepare Python Environments does all of this).
import ch.epfl.biop.atlas.aligner.DeepSliceHelper
import ch.epfl.biop.atlas.brainglobe.BrainGlobeAppose
import ch.epfl.biop.wrappers.elastix.ApposeElastixTask

import java.util.function.Consumer

def wanted = (args ? args[0] : "none").split(",").findAll { it && it != "none" } as Set
def failed = []

def step = { String key, String name, Closure build ->
    println "ABBA_PHASE ${key} start"
    println "ABBA_PREPARE ${name}: building (already built: a few seconds)..."
    long start = System.currentTimeMillis()
    try {
        build()
        println "ABBA_PREPARE ${name}: ready (${(System.currentTimeMillis() - start).intdiv(1000)} s)"
    } catch (Throwable e) {
        println "ABBA_PREPARE ${name}: FAILED - ${e.message}"
        e.printStackTrace(System.out)
        failed << name
    } finally {
        println "ABBA_PHASE ${key} done"
    }
}

def say = { String line -> if (line?.trim()) println "ABBA_PREPARE_LOG ${line.trim()}" } as Consumer<String>

if ("deepslice" in wanted) step("deepslice", "DeepSlice v${DeepSliceHelper.ApposeDeepSliceTask.DS_VERSION}") {
    DeepSliceHelper.ApposeDeepSliceTask.environment(say)
}
if ("elastix" in wanted) step("elastix", "Elastix (itk-elastix v${ApposeElastixTask.ITK_ELASTIX_VERSION})") {
    ApposeElastixTask.getElastixApposeService()
}
if ("brainglobe" in wanted) step("brainglobe", "BrainGlobe atlas API v${BrainGlobeAppose.BG_VERSION}") {
    def brainglobe = new BrainGlobeAppose()
    brainglobe.setProgressCallback(say)
    brainglobe.getOrCreateEnvironment()
}

println "ABBA_PREPARE " + (failed ? "failed: " + failed.join(", ") : "done")
System.exit(failed ? 1 : 0)
