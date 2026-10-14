// Batchmode WebGL build for playbench:
//   Unity.exe -batchmode -nographics -quit -projectPath examples/dodge-unity -buildTarget WebGL
//             -executeMethod BuildWebGL.Build -logFile build.log
// Output: examples/dodge-unity/Build (index.html at its root), uncompressed so any static server works.
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class BuildWebGL
{
    public static void Build()
    {
        const string scene = "Assets/Main.unity"; // empty: Dodge.cs boots itself via RuntimeInitializeOnLoadMethod
        if (!System.IO.File.Exists(scene))
            EditorSceneManager.SaveScene(EditorSceneManager.NewScene(NewSceneSetup.EmptyScene), scene);
        PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
        PlayerSettings.WebGL.decompressionFallback = false;
        PlayerSettings.WebGL.dataCaching = false; // IndexedDB cache would hide harness file overrides
        PlayerSettings.defaultWebScreenWidth = 480;
        PlayerSettings.defaultWebScreenHeight = 320;
        var r = BuildPipeline.BuildPlayer(new[] { scene }, "Build", BuildTarget.WebGL, BuildOptions.None);
        Debug.Log($"PLAYBENCH BUILD {r.summary.result} in {r.summary.totalTime} ({r.summary.totalSize} bytes)");
        EditorApplication.Exit(r.summary.result == BuildResult.Succeeded ? 0 : 1);
    }
}
