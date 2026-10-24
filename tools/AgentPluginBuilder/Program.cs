using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Skyrim;

if(args.Length!=1)throw new ArgumentException("Supply a staging output path for WhiterunAgents.esp");
var output=Path.GetFullPath(args[0]);
if(Path.GetFileName(output) is "WhiterunRouter.esp" or "WhiterunRest.esp"){RouterBuilder.Build(output);return;}
if(Path.GetFileName(output)!="WhiterunAgents.esp")throw new ArgumentException("Unexpected plugin filename");
var key=ModKey.FromNameAndExtension("WhiterunAgents.esp");
var master=ModKey.FromNameAndExtension("Skyrim.esm");
var mod=new SkyrimMod(key,SkyrimRelease.SkyrimSE);
uint[] residents={108186,108149,108156};
uint routeIndex=0;
foreach(var resident in residents)foreach(var destination in residents){
if(resident==destination)continue;
var quest=new Quest(new FormKey(key,0x800+routeIndex*2),SkyrimRelease.SkyrimSE){
 EditorID=$"WSAgentRoutine{routeIndex}",Name="Whiterun Society agent routine",Priority=95,
 Flags=0,NextAliasID=2
};
var travel=new Package(new FormKey(key,0x801+routeIndex*2),SkyrimRelease.SkyrimSE){
 EditorID=$"WSAgentTravel{routeIndex}",Type=Package.Types.Package,
 Flags=Package.Flag.PreferredSpeed,PreferredSpeed=Package.Speed.Walk,
 ScheduleMonth=-1,ScheduleDayOfWeek=Package.DayOfWeek.Any,ScheduleDate=0,
 ScheduleHour=-1,ScheduleMinute=-1,ScheduleDurationInMinutes=0,
 DataInputVersion=3,XnamMarker=new byte[]{5},Unknown3=new byte[]{0,0,0}
};
travel.OwnerQuest.SetTo(quest.FormKey);
// Reference the owned game's standard Travel template; do not redistribute it.
travel.PackageTemplate.SetTo(new FormKey(master,0x16FAA));
travel.Data[0]=new PackageDataLocation{Location=new LocationTargetRadius{
 Target=new LocationFallback{Type=LocationTargetRadius.LocationType.AliasForReference,Data=1},Radius=150}};
travel.Data[2]=new PackageDataBool{Data=false};
travel.Data[4]=new PackageDataBool{Data=false};
var actor=new QuestAlias{ID=0,Name="ManagedResident",Type=QuestAlias.TypeEnum.Reference,
 Flags=QuestAlias.Flag.AllowReserved};
actor.ForcedReference.SetTo(new FormKey(master,resident));
actor.PackageData.Add(travel.FormKey);
quest.Aliases.Add(actor);
var target=new QuestAlias{ID=1,Name="AgentDestination",Type=QuestAlias.TypeEnum.Reference,
 Flags=QuestAlias.Flag.AllowReserved|QuestAlias.Flag.AllowReuseInQuest};
target.ForcedReference.SetTo(new FormKey(master,destination));
quest.Aliases.Add(target);
mod.Quests.Add(quest);mod.Packages.Add(travel);
routeIndex++;
}
Directory.CreateDirectory(Path.GetDirectoryName(output)!);
mod.WriteToBinary(output);
using var check=SkyrimMod.CreateFromBinaryOverlay(output,SkyrimRelease.SkyrimSE);
if(check.Quests.Count!=6||check.Packages.Count!=6||check.Quests.Any(q=>q.Aliases.Count!=2))
 throw new InvalidDataException("Plugin readback failed");
Console.WriteLine($"Built six original resident travel tasks: {output}");
