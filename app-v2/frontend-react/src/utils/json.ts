export const utilsJson = {
  stringify: (data: unknown) => {
    try {
      return JSON.stringify(data, null, 2);
    } catch (error) {
      console.log('utilsJson.stringify - Error');
      console.error(error);
      console.log('utilsJson.stringify - Input Data');
      console.log(data);
      return "Invalid JSON";
    }
  },
  parse: (data: string) => {
    try {
      return JSON.parse(data);
    } catch (error) {
      console.log('utilsJson.parse - Error');
      console.error(error);
      console.log('utilsJson.parse - Input Data');
      console.log(data);
      return {};
    }
  }
};