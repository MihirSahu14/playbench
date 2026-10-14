// dodge-unity: Unity WebGL twin of examples/dodge-web for the playbench harness.
// Arrows move, Enter (or click) starts/restarts, survive 20 s to win. Enemies come from StreamingAssets/enemies.csv.
// URL switches: ?bug=crash (C# throws every frame after 5 s), ?bug=jscrash (JS throw after 5 s),
// ?bug=softlock (world freezes at 8 s), ?noprobe, ?nobot (handled in Plugins/PlaybenchProbe.jslib).
using System;
using System.Collections;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

public class Dodge : MonoBehaviour
{
#if UNITY_WEBGL && !UNITY_EDITOR
    [DllImport("__Internal")] static extern void PB_SetState(string json);
    [DllImport("__Internal")] static extern int PB_Seed();
    [DllImport("__Internal")] static extern float PB_Override(string name, float def);
    [DllImport("__Internal")] static extern string PB_Query(string name);
    [DllImport("__Internal")] static extern void PB_Crash();
#else
    static void PB_SetState(string json) { }
    static int PB_Seed() => -1;
    static float PB_Override(string name, float def) => def;
    static string PB_Query(string name) => "";
    static void PB_Crash() { }
#endif

    const float W = 480, H = 320, PW = 16, PY = H - PW - 4, PCY = PY + PW / 2, WIN_S = 20, PS = 4; // px/frame at 60 fps
    class Kind { public string id; public float speed, size, spawnMs, timer; }
    class Enemy { public float x, y; public Kind k; }

    List<Kind> kinds;
    readonly List<Enemy> enemies = new List<Enemy>();
    readonly StringBuilder sb = new StringBuilder();
    bool started, over, won;
    float playT, px = W / 2, speedMul;
    string bug;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Boot() => new GameObject("Dodge").AddComponent<Dodge>(); // ponytail: no scene content, code builds it

    IEnumerator Start()
    {
        var cam = new GameObject("Camera").AddComponent<Camera>();
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color(.07f, .07f, .07f);
        int seed = PB_Seed();
        UnityEngine.Random.InitState(seed >= 0 ? seed : Environment.TickCount);
        speedMul = PB_Override("enemy_speed", 1f); // knob: multiplies every enemy's CSV speed
        bug = PB_Query("bug");

        var path = Application.streamingAssetsPath + "/enemies.csv";
        using (var r = UnityWebRequest.Get(path.Contains("://") ? path : "file://" + path))
        {
            yield return r.SendWebRequest();
            if (r.result != UnityWebRequest.Result.Success) { Debug.LogError("enemies.csv: " + r.error); yield break; }
            var rows = r.downloadHandler.text.Trim().Split('\n');
            var head = Array.ConvertAll(rows[0].Split(','), s => s.Trim());
            var list = new List<Kind>();
            for (int i = 1; i < rows.Length; i++)
            {
                var c = rows[i].Split(',');
                float F(string col) => float.Parse(c[Array.IndexOf(head, col)].Trim(), System.Globalization.CultureInfo.InvariantCulture);
                list.Add(new Kind { id = c[0].Trim(), speed = F("speed"), size = F("size"), spawnMs = F("spawn_ms") });
            }
            kinds = list;
        }
    }

    void Update()
    {
        if (bug == "crash" && playT >= 5) throw new InvalidOperationException("planted crash");
        if (bug == "jscrash" && playT >= 5) PB_Crash();
        bool go = Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter) || Input.GetMouseButtonDown(0);
        if (go && over) { enemies.Clear(); playT = 0; px = W / 2; over = won = false; kinds?.ForEach(k => k.timer = 0); }
        if (go) started = true;
        if (started && !over && kinds != null && !(bug == "softlock" && playT >= 8)) Step(Time.deltaTime);
        PB_SetState(StateJson());
    }

    void Step(float dt)
    {
        playT += dt;
        px += ((Input.GetKey(KeyCode.RightArrow) ? 1 : 0) - (Input.GetKey(KeyCode.LeftArrow) ? 1 : 0)) * PS * 60 * dt;
        px = Mathf.Clamp(px, PW / 2, W - PW / 2);
        foreach (var k in kinds)
        {
            k.timer += dt * 1000;
            if (k.timer < k.spawnMs) continue;
            k.timer -= k.spawnMs;
            enemies.Add(new Enemy { x = k.size / 2 + UnityEngine.Random.value * (W - k.size), y = -k.size / 2, k = k });
        }
        foreach (var e in enemies) e.y += e.k.speed * speedMul * 60 * dt;
        enemies.RemoveAll(e => e.y - e.k.size / 2 >= H);
        foreach (var e in enemies)
        {
            float r = (e.k.size + PW) / 2;
            if (Mathf.Abs(e.x - px) < r && Mathf.Abs(e.y - PCY) < r) { over = true; won = false; return; }
        }
        if (playT >= WIN_S) { over = true; won = true; }
    }

    int Score => Mathf.FloorToInt(Mathf.Min(playT, WIN_S));

    // Probe contract: {over, won, score, paused, px, enemies:[[x,y]...]}, logical 480x320 px, y grows downward.
    string StateJson()
    {
        sb.Clear().Append("{\"over\":").Append(over ? "true" : "false").Append(",\"won\":").Append(won ? "true" : "false")
          .Append(",\"paused\":").Append(!started || kinds == null ? "true" : "false").Append(",\"score\":").Append(Score)
          .Append(",\"px\":").Append(Mathf.RoundToInt(px)).Append(",\"enemies\":[");
        for (int i = 0; i < enemies.Count; i++)
            sb.Append(i > 0 ? ",[" : "[").Append(Mathf.RoundToInt(enemies[i].x)).Append(',').Append(Mathf.RoundToInt(enemies[i].y)).Append(']');
        return sb.Append("]}").ToString();
    }

    void OnGUI()
    {
        GUI.matrix = Matrix4x4.Scale(new Vector3(Screen.width / W, Screen.height / H, 1));
        foreach (var e in enemies)
            Box(e.x - e.k.size / 2, e.y - e.k.size / 2, e.k.size, e.k.size, e.k.id == "bat" ? new Color(.85f, .33f, .33f) : new Color(.33f, .8f, .33f));
        Box(px - PW / 2, PY, PW, PW, new Color(.33f, .67f, 1f));
        GUI.color = Color.white;
        var mid = new GUIStyle(GUI.skin.label) { alignment = TextAnchor.MiddleCenter };
        GUI.Label(new Rect(0, 4, W, 20), "score " + Score, mid);
        var msg = !started ? "Press Enter or click to start" : kinds == null ? "loading..."
            : over ? (won ? "You survived! " : "Hit! ") + "Score " + Score + " - Enter to restart" : "";
        if (msg != "") { Box(0, H / 2 - 22, W, 44, new Color(0, 0, 0, .6f)); GUI.color = Color.white; GUI.Label(new Rect(0, H / 2 - 22, W, 44), msg, mid); }
    }

    static void Box(float x, float y, float w, float h, Color c)
    {
        GUI.color = c;
        GUI.DrawTexture(new Rect(x, y, w, h), Texture2D.whiteTexture);
    }
}
