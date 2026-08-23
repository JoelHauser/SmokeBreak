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

                var handsPrefab = root.GetComponentInChildren<UsableHandsPrefab>(true);
                if (handsPrefab == null || handsPrefab.ItemSpawnTransform == null)
                {
                    SmokeBreakPlugin.Log.LogWarning("[SmokeBreak] no UsableHandsPrefab/ItemSpawnTransform found.");
                    return;
                }

                var prefab = PackModels.Get(templateId);
                if (prefab == null) return;

                // Hide whatever the borrowed container was carrying. Disabling
                // rather than destroying, because the controller still owns it
                // and may touch it on teardown.
                foreach (var renderer in handsPrefab.Renderers)
                {
                    if (renderer != null) renderer.enabled = false;
                }

                var mount = handsPrefab.ItemSpawnTransform;
                var instance = UnityEngine.Object.Instantiate(prefab, mount, false);
                instance.name = "SmokeBreak_" + prefab.name;
                instance.transform.localPosition = Vector3.zero;
                instance.transform.localRotation = Quaternion.identity;

                SmokeBreakPlugin.Log.LogInfo(
                    "[SmokeBreak] mounted " + instance.name + " on " + mount.name + " for " + templateId);
            }
            catch (Exception ex)
            {
                // Never let a cosmetic swap take the raid down with it.
                SmokeBreakPlugin.Log.LogError("[SmokeBreak] swap failed: " + ex);
            }
        }
    }
}
