using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using BepInEx;
using BepInEx.Logging;
using EFT;
using EFT.InventoryLogic;
using HarmonyLib;
using UnityEngine;

namespace SmokeBreakClient
{
    /// <summary>
    /// Puts a cigarette pack in the player's hands.
    ///
    /// The server mod leaves UsePrefab pointing at a real EFT usable_items
    /// container, so the hands, the animator and the eat animation are all BSG's
    /// and are known to work. This plugin only swaps the visible model.
    ///
    /// That distinction matters. A UsePrefab bundle is not a model - the vanilla
    /// slickers container carries 131 GameObjects: both arms, every digit, an
    /// AnimatorController, three AnimationClips and a UsableHandsPrefab
    /// component. Shipping a bare mesh as a UsePrefab makes the client hang
    /// while it waits for parts that are not there. Loading our own bundle
    /// ourselves avoids that entirely, because EFT never treats it as a hands
    /// prefab.
    /// </summary>
    [BepInPlugin(PluginGuid, PluginName, PluginVersion)]
    public class SmokeBreakPlugin : BaseUnityPlugin
    {
        public const string PluginGuid = "com.mybutthasarash.smokebreak.client";
        public const string PluginName = "Smoke Break (client)";
        public const string PluginVersion = "0.3.0";

        internal static ManualLogSource Log;
        internal static string BundleDir;

        private void Awake()
        {
            Log = Logger;
            BundleDir = Path.Combine(Path.GetDirectoryName(Info.Location) ?? ".", "bundles");

            if (!Directory.Exists(BundleDir))
            {
                Log.LogWarning("[SmokeBreak] no bundles folder at " + BundleDir + "; packs will not be swapped in.");
            }

            new Harmony(PluginGuid).PatchAll(typeof(SpawnPatch));
            Log.LogInfo("[SmokeBreak] client loaded, bundles from " + BundleDir);
        }
    }

    /// <summary>Loads and caches our pack bundles, one prefab each.</summary>
    internal static class PackModels
    {
        // Template id -> bundle file. These are the four cigarette items.
        private static readonly Dictionary<string, string> Bundles = new Dictionary<string, string>
        {
            { "573475fb24597737fb1379e1", "pack_apollosoyuz.bundle" },
            { "573476d324597737da2adc13", "pack_malboro.bundle" },
            { "5734770f24597738025ee254", "pack_strike.bundle" },
            { "573476f124597737e04bf328", "pack_wilston.bundle" },
        };

        private static readonly Dictionary<string, GameObject> Cache = new Dictionary<string, GameObject>();

        internal static bool Handles(string templateId)
        {
            return templateId != null && Bundles.ContainsKey(templateId);
        }

        internal static GameObject Get(string templateId)
        {
            if (templateId == null) return null;
            if (Cache.TryGetValue(templateId, out var cached)) return cached;

            if (!Bundles.TryGetValue(templateId, out var file)) return null;

            var path = Path.Combine(SmokeBreakPlugin.BundleDir, file);
            if (!File.Exists(path))
            {
                SmokeBreakPlugin.Log.LogWarning("[SmokeBreak] missing bundle: " + path);
                Cache[templateId] = null;
                return null;
            }

            try
            {
                // LoadFromFile rather than going through SPT's bundle system.
                // Nothing else needs to know this bundle exists.
                var bundle = AssetBundle.LoadFromFile(path);
                if (bundle == null)
                {
                    SmokeBreakPlugin.Log.LogError("[SmokeBreak] could not open bundle: " + file);
                    Cache[templateId] = null;
                    return null;
                }

                var prefabs = bundle.LoadAllAssets<GameObject>();
                var prefab = prefabs != null && prefabs.Length > 0 ? prefabs[0] : null;
                if (prefab == null)
                {
                    SmokeBreakPlugin.Log.LogError("[SmokeBreak] bundle has no GameObject: " + file);
                }
                else
                {
                    SmokeBreakPlugin.Log.LogInfo("[SmokeBreak] loaded " + prefab.name + " from " + file);
                }

                Cache[templateId] = prefab;
                return prefab;
            }
            catch (Exception ex)
            {
                SmokeBreakPlugin.Log.LogError("[SmokeBreak] failed loading " + file + ": " + ex.Message);
                Cache[templateId] = null;
                return null;
            }
        }
    }

    /// <summary>
    /// After the controller spawns its in-hands object, hide the borrowed model
    /// and mount ours on the same transform.
    /// </summary>
    internal static class SpawnPatch
    {
        private static readonly FieldInfo ItemField =
            AccessTools.Field(typeof(Player.ItemHandsController), "_item");

        private static readonly FieldInfo ControllerObjectField =
            AccessTools.Field(typeof(Player.ItemHandsController), "_controllerObject");

        [HarmonyPatch(typeof(Player.MedsController), nameof(Player.MedsController.Spawn))]
        [HarmonyPostfix]
        private static void AfterSpawn(Player.MedsController __instance)
        {
            try
            {
                var item = ItemField?.GetValue(__instance) as Item;
                if (item == null) return;

                var templateId = item.TemplateId.ToString();
                if (!PackModels.Handles(templateId)) return;

                var root = ControllerObjectField?.GetValue(__instance) as GameObject;
                if (root == null)
                {
                    SmokeBreakPlugin.Log.LogWarning("[SmokeBreak] no controller object to attach to.");
                    return;
                }

                // The controller object is not necessarily the prefab root, so try
                // downwards, then upwards, then the scene. Logged either way,
                // because "not found" on its own says nothing about where to look.
                var handsPrefab = root.GetComponentInChildren<UsableHandsPrefab>(true)
                                  ?? root.GetComponentInParent<UsableHandsPrefab>()
                                  ?? UnityEngine.Object.FindObjectOfType<UsableHandsPrefab>();

                if (handsPrefab == null)
                {
                    SmokeBreakPlugin.Log.LogWarning("[SmokeBreak] no UsableHandsPrefab anywhere. Controller object was '"
                        + root.name + "'. Hierarchy follows:");
                    DumpHierarchy(root.transform, 0, 3);

                    var anyWeaponPrefab = root.GetComponentInChildren<WeaponPrefab>(true);
                    SmokeBreakPlugin.Log.LogWarning("[SmokeBreak] WeaponPrefab in children: "
                        + (anyWeaponPrefab == null ? "none" : anyWeaponPrefab.GetType().Name));
                    return;
                }

                if (handsPrefab.ItemSpawnTransform == null)
                {
                    // The component exists but has no mount point. Fall back to
                    // the transform the borrowed model actually hangs on.
                    SmokeBreakPlugin.Log.LogWarning("[SmokeBreak] ItemSpawnTransform is null on "
                        + handsPrefab.name + "; falling back to the first renderer's transform.");
                    // NOT simply the first renderer. Renderers comes from
                    // WeaponPrefab, and its first entry is MuzzleJetCombinedMesh -
                    // an invisible muzzle-flash mesh every weapon prefab carries.
                    // Mounting there put the pack on nothing, and disabling the
                    // whole list took the real model with it.
                    var model = PickItemRenderer(handsPrefab);
                    if (model != null)
                    {
                        MountOn(model.transform, handsPrefab, templateId);
                        return;
                    }
                    SmokeBreakPlugin.Log.LogWarning("[SmokeBreak] no item renderer among "
                        + handsPrefab.Renderers.Length + ": " + DescribeRenderers(handsPrefab));
                    SmokeBreakPlugin.Log.LogWarning("[SmokeBreak] no renderers to fall back to either.");
                    return;
                }

                MountOn(handsPrefab.ItemSpawnTransform, handsPrefab, templateId);
            }
            catch (Exception ex)
            {
                // Never let a cosmetic swap take the raid down with it.
                SmokeBreakPlugin.Log.LogError("[SmokeBreak] swap failed: " + ex);
            }
        }

        private static void MountOn(Transform mount, UsableHandsPrefab handsPrefab, string templateId)
        {
            var prefab = PackModels.Get(templateId);
            if (prefab == null || mount == null) return;

            // Hide every part of the borrowed item, not just the largest. The
            // sugar container is a box, a cap and nine loose cubes; hiding only
            // the box would leave the cubes floating in mid air. Effect meshes
            // are left alone, which is what blanking the whole list got wrong.
            foreach (var r in handsPrefab.Renderers)
            {
                if (r == null) continue;
                var n = r.gameObject.name;
                if (n.IndexOf("muzzle", StringComparison.OrdinalIgnoreCase) >= 0) continue;
                if (n.IndexOf("jet", StringComparison.OrdinalIgnoreCase) >= 0) continue;
                if (n.IndexOf("shell", StringComparison.OrdinalIgnoreCase) >= 0) continue;
                r.enabled = false;
            }

            var instance = UnityEngine.Object.Instantiate(prefab, mount, false);
            instance.name = "SmokeBreak_" + prefab.name;
            instance.transform.localPosition = Vector3.zero;
            instance.transform.localRotation = Quaternion.identity;

            // Report where it actually landed. "Mounted" on its own told us
            // nothing last time - the pack was mounted and invisible.
            var bounds = "no renderer";
            var rend = instance.GetComponentInChildren<Renderer>(true);
            if (rend != null)
            {
                bounds = "world " + rend.bounds.center.ToString("F3") + " size " + rend.bounds.size.ToString("F3");
            }

            SmokeBreakPlugin.Log.LogInfo(
                "[SmokeBreak] mounted " + instance.name + " on " + mount.name
                + " | mount world " + mount.position.ToString("F3")
                + " | " + bounds);
        }

        /// <summary>
        /// The held item's renderer, told apart from the effect meshes a weapon
        /// prefab always carries. EFT names item meshes item_&lt;thing&gt;_LOD0, so
        /// prefer those and never take a muzzle or jet mesh.
        /// </summary>
        private static Renderer PickItemRenderer(UsableHandsPrefab handsPrefab)
        {
            Renderer best = null;
            var bestSize = -1f;

            foreach (var r in handsPrefab.Renderers)
            {
                if (r == null) continue;
                var name = r.gameObject.name;
                if (name.IndexOf("muzzle", StringComparison.OrdinalIgnoreCase) >= 0) continue;
                if (name.IndexOf("jet", StringComparison.OrdinalIgnoreCase) >= 0) continue;
                if (name.IndexOf("shell", StringComparison.OrdinalIgnoreCase) >= 0) continue;

                // Prefer a name that looks like an item mesh; otherwise fall back
                // to the largest remaining renderer, which is the model itself.
                var looksLikeItem = name.StartsWith("item_", StringComparison.OrdinalIgnoreCase);
                var size = r.bounds.size.magnitude + (looksLikeItem ? 1000f : 0f);
                if (size > bestSize)
                {
                    bestSize = size;
                    best = r;
                }
            }

            return best;
        }

        private static string DescribeRenderers(UsableHandsPrefab handsPrefab)
        {
            var names = new List<string>();
            foreach (var r in handsPrefab.Renderers)
            {
                names.Add(r == null ? "<null>" : r.gameObject.name);
            }
            return string.Join(", ", names.ToArray());
        }

        private static void DumpHierarchy(Transform t, int depth, int maxDepth)
        {
            if (t == null || depth > maxDepth) return;
            var components = "";
            foreach (var c in t.GetComponents<Component>())
            {
                if (c != null) components += c.GetType().Name + " ";
            }
            SmokeBreakPlugin.Log.LogWarning("[SmokeBreak]   " + new string(' ', depth * 2) + t.name + "  [" + components.Trim() + "]");
            for (var i = 0; i < t.childCount && i < 12; i++)
            {
                DumpHierarchy(t.GetChild(i), depth + 1, maxDepth);
            }
        }
    }
}
