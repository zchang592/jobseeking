import { JobBrowser, SearchParams } from "@/components/JobBrowser";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  return <JobBrowser params={await searchParams} saved />;
}
